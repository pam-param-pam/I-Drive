import { noWifi } from "@/axios/helper.js"
import { PipelineWorker } from "@/transfers/shared/base/PipelineWorker.js"
import { workerExitReason } from "@/transfers/shared/constants.js"
import { downloadFileStatus, downloadState } from "@/transfers/downloads/constants.js"
import throttle from "lodash.throttle"


export class HttpDownloadError extends Error {
   constructor(status, statusText) {
      super(`Download failed: HTTP ${status}`)
      this.name = "HttpDownloadError"
      this.status = status
      this.statusText = statusText
   }
}


export class FileConsumer extends PipelineWorker {
   constructor({ fileQueue, downloadRuntime }) {
      super()

      this.fileQueue = fileQueue
      this.downloadRuntime = downloadRuntime

      this.activeController = null
      this.activeAbortReason = null
      this.failedRequests = new Map()
   }

   kill() {
      this.abortActiveDownload()
      return super.kill()
   }

   async run() {
      if (this._running) {
         console.warn("DownloadConsumer is already running!")
         return workerExitReason.stopped
      }

      const signal = this._markStarted()
      let exitReason = workerExitReason.stopped

      try {
         while (!signal.aborted) {
            if (this._stopRequested) {
               exitReason = workerExitReason.stopped
               break
            }

            if (this.downloadRuntime.downloadState !== downloadState.downloading) {
               await this.downloadRuntime.waitUntilResumed(signal)
               continue
            }

            const queueItem = await this.takeWithAbort(this.fileQueue, signal)

            if (!queueItem) {
               exitReason = workerExitReason.inputEnded
               break
            }

            await this.downloadFile(queueItem, signal)
         }

         if (exitReason === workerExitReason.inputEnded) {
            this.fileQueue.close()
         }

         if (this._killed) {
            exitReason = workerExitReason.killed
         }

         return exitReason
      } catch (err) {
         exitReason = this._handleRunError(err)
         return exitReason
      } finally {
         this.clearActiveDownload()
         this._markFinished(exitReason)
      }
   }

   async downloadFile(queueItem, workerSignal) {
      this.activeController = new AbortController()
      this.activeAbortReason = null

      const { file } = queueItem
      const signal = this.mergeAbortSignals(workerSignal, this.activeController.signal)

      try {
         this.downloadRuntime.getFileState(file.id)?.setStatus(downloadFileStatus.downloading)

         const response = await this.fetchFile(queueItem, signal)
         await this.validateResponse(response, queueItem)

         if (!response.body) {
            throw new Error("Download failed: response has no body")
         }

         await this.saveResponseToDisk(response, queueItem, signal)

         if (signal.aborted) {
            throw new DOMException("Aborted", "AbortError")
         }

         if (queueItem.offset !== file.size) {
            throw new Error(`Download incomplete. Expected ${file.size} bytes, got ${queueItem.offset} bytes`)
         }

         console.log("downloadFile finishExistingFile")
         this.failedRequests.delete(file.id)
         this.downloadRuntime.finishExistingFile(file.id)
      } catch (err) {
         await this.handleDownloadError(err, queueItem, workerSignal)
      } finally {
         this.clearActiveDownload()
      }
   }

   async fetchFile(queueItem, signal) {
      const options = { signal }

      if (queueItem.offset > 0) {
         options.headers = {
            Range: `bytes=${queueItem.offset}-`
         }
      }

      return await fetch(`/raw-file/${queueItem.file.id}`, options)
   }

   async validateResponse(response, queueItem) {
      if (!response.ok) {
         throw new HttpDownloadError(response.status, response.statusText)
      }

      const expectedSize = queueItem.file.size - queueItem.offset
      const contentLength = response.headers.get("content-length")

      if (contentLength !== null && Number(contentLength) !== expectedSize) {
         throw new Error(`Download failed: size mismatch. Expected ${expectedSize} bytes, got ${contentLength} bytes`)
      }
   }

   async saveResponseToDisk(response, queueItem, signal) {
      const { file } = queueItem
      const totalBytes = file.size
      const reader = response.body.getReader()
      const writable = await queueItem.fileHandle.createWritable({ keepExistingData: queueItem.offset > 0 })

      try {
         if (queueItem.offset > 0) {
            await writable.seek(queueItem.offset)
         }

         while (true) {
            if (signal.aborted) {
               throw new DOMException("Aborted", "AbortError")
            }

            if (this.downloadRuntime.downloadState !== downloadState.downloading) {
               await this.downloadRuntime.waitUntilResumed(signal)
               continue
            }

            const { value, done } = await reader.read()

            if (signal.aborted) {
               throw new DOMException("Aborted", "AbortError")
            }

            if (done) {
               break
            }

            await writable.write(value)

            queueItem.offset += value.byteLength
            this.emitProgress(file, queueItem.offset, totalBytes)
         }

         this.emitProgress.flush()
      } finally {
         this.emitProgress.cancel()
         reader.releaseLock()
         await writable.close()
      }
   }

   emitProgress = throttle((file, downloadedBytes, totalBytes) => {
      this.downloadRuntime.onDownloadProgress(file.id, {
         loaded: downloadedBytes,
         total: totalBytes,
         downloadedBytes,
         totalBytes
      })
   }, 100, { leading: true, trailing: true })

   async handleDownloadError(err, queueItem, workerSignal) {
      console.log("handleDownloadError")
      console.error(err)
      const { file } = queueItem
      const fileState = this.downloadRuntime.getFileState(file.id)

      if (this.isPauseAbort(err)) {
         await this.requeueFirst(queueItem, workerSignal)
         return
      }

      if (this.isAbort(err) || workerSignal?.aborted || this._killed) {
         return
      }

      if (noWifi(err)) {
         fileState.setStatus(downloadFileStatus.retrying)
         await this.requeueFirst(queueItem, workerSignal)
         return
      }

      if (err instanceof HttpDownloadError) {
         this.failedRequests.set(file.id, queueItem)
         fileState.setStatus(downloadFileStatus.errorOccurred)
         fileState.setError(err?.message ?? "Download failed")
         return
      }

      fileState.setStatus(downloadFileStatus.failed)
      fileState.setError(err?.message ?? "Download failed")

   }

   async retryFile(fileId) {
      const queueItem = this.failedRequests.get(fileId)

      if (!queueItem) {
         return false
      }

      this.failedRequests.delete(fileId)

      const fileState = this.downloadRuntime.getFileState(fileId)
      fileState.setStatus(downloadFileStatus.retrying)

      await this.requeueFirst(queueItem)

      return true
   }

   async requeueFirst(queueItem, signal) {
      await this.putWithAbort(this.fileQueue, queueItem, signal, { first: true })
   }

   pauseActiveDownload() {
      if (!this.activeController) {
         return
      }

      this.activeAbortReason = "pause"
      this.activeController.abort()
   }

   abortActiveDownload() {
      this.activeAbortReason = null
      this.activeController?.abort()
   }

   clearActiveDownload() {
      this.activeController = null
      this.activeAbortReason = null
   }

   isPauseAbort(err) {
      return this.activeAbortReason === "pause" && this.isAbort(err)
   }

   isAbort(err) {
      return err?.name === "AbortError" || err?.aborted === true
   }

   mergeAbortSignals(...signals) {
      const controller = new AbortController()

      for (const signal of signals) {
         if (!signal) {
            continue
         }

         if (signal.aborted) {
            controller.abort()
            break
         }

         signal.addEventListener("abort", () => controller.abort(), { once: true })
      }

      return controller.signal
   }
}