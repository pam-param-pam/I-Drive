import { noWifi } from "@/axios/helper.js"
import { PipelineWorker } from "@/transfers/shared/base/PipelineWorker.js"
import { workerExitReason } from "@/transfers/shared/constants.js"
import { downloadFileStatus, downloadState } from "@/transfers/downloads/constants.js"
import throttle from "lodash.throttle"

export class DownloadConsumer extends PipelineWorker {
   constructor({ downloadQueue, downloadRuntime }) {
      super()

      this.downloadQueue = downloadQueue
      this.downloadRuntime = downloadRuntime

      this.activeController = null
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
               exitReason = this._killed ? workerExitReason.killed : workerExitReason.stopped
               break
            }

            if (this.downloadRuntime.downloadState !== downloadState.downloading) {
               await this.downloadRuntime.waitUntilResumed(signal)
               continue
            }

            const file = await this.takeWithAbort(this.downloadQueue, signal)

            if (!file) {
               exitReason = workerExitReason.inputEnded
               break
            }

            await this.downloadFile(file, signal)
         }

         if (exitReason === workerExitReason.inputEnded) {
            this.downloadQueue.close?.()
         }

         if (this._killed) {
            exitReason = workerExitReason.killed
         }

         return exitReason
      } catch (err) {
         exitReason = this._handleRunError(err)
         return exitReason
      } finally {
         this.activeController = null
         this._markFinished(exitReason)
      }
   }

   async downloadFile(file, workerSignal) {
      this.activeController = new AbortController()

      const signal = this._mergeAbortSignals(workerSignal, this.activeController.signal)

      try {
         this._setFileStatus(file.id, downloadFileStatus.downloading)

         const response = await fetch(`/video/${encodeURIComponent(file.id)}`, { signal })

         if (!response.ok) {
            throw new Error(`Download failed: HTTP ${response.status}`)
         }

         await this.saveResponseToDisk(response, file, signal)

         this.downloadRuntime.markFileDownloaded(file.id)
      } catch (err) {
         await this.handleDownloadError(err, file, workerSignal)
      } finally {
         this.activeController = null
      }
   }

   async saveResponseToDisk(response, file, signal) {
      if (!response.body) {
         throw new Error("Download failed: response has no body")
      }

      const totalBytes = this._getTotalBytes(response, file)
      const reader = response.body.getReader()
      const writable = await this.openWritableFile(file)

      let downloadedBytes = 0
      let completed = false

      try {
         while (true) {
            if (signal?.aborted) {
               throw this._makeAbortError()
            }

            if (this.downloadRuntime.downloadState !== downloadState.downloading) {
               await this.downloadRuntime.waitUntilResumed(signal)
            }

            const { value, done } = await reader.read()
            if (done) break

            await writable.write(value)

            downloadedBytes += value.byteLength
            this.emitProgress(file, downloadedBytes, totalBytes)
         }

         this.emitProgress.flush()
         completed = true
      } finally {
         this.emitProgress.cancel()
         reader.releaseLock()

         if (completed) {
            await writable.close()
         } else {
            await this._abortWritable(writable)
         }
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

   async openWritableFile(file) {
      if (file.fileHandle) {
         return await file.fileHandle.createWritable()
      }

      if (file.directoryHandle) {
         file.fileHandle = await file.directoryHandle.getFileHandle(file.name, { create: true })
         return await file.fileHandle.createWritable()
      }

      file.fileHandle = await window.showSaveFilePicker({
         suggestedName: file.name
      })

      return await file.fileHandle.createWritable()
   }

   async handleDownloadError(err, file, signal) {
      if (signal?.aborted || this._killed || err.name === "AbortError" || err.aborted) {
         this._setFileStatus(file.id, downloadFileStatus.aborted ?? downloadFileStatus.error)
         return
      }

      if (noWifi(err)) {
         this._setFileStatus(file.id, downloadFileStatus.waitingForInternet ?? downloadFileStatus.error)
         await this.putWithAbort(this.downloadQueue, file, signal, true)
         return
      }

      this._setFileStatus(file.id, downloadFileStatus.error)
      this._setFileError(file.id, err.message ?? err)
   }

   abortActiveDownload() {
      this.activeController?.abort()
   }

   _setFileStatus(fileId, status) {
      this.downloadRuntime.getFileState(fileId)?.setStatus(status)
   }

   _setFileError(fileId, error) {
      this.downloadRuntime.getFileState(fileId)?.setError?.(error)
   }

   _getTotalBytes(response, file) {
      const contentLength = Number(response.headers.get("content-length"))
      return Number.isFinite(contentLength) && contentLength > 0 ? contentLength : file.size ?? 0
   }

   _makeAbortError() {
      const err = new Error("Download aborted")
      err.name = "AbortError"
      err.aborted = true
      return err
   }

   async _abortWritable(writable) {
      try {
         if (writable.abort) {
            await writable.abort()
         } else {
            await writable.close()
         }
      } catch {
         // ignored intentionally; original download error is more important
      }
   }

   _mergeAbortSignals(...signals) {
      const controller = new AbortController()

      for (const signal of signals) {
         if (!signal) continue

         if (signal.aborted) {
            controller.abort()
            break
         }

         signal.addEventListener("abort", () => controller.abort(), { once: true })
      }

      return controller.signal
   }
}