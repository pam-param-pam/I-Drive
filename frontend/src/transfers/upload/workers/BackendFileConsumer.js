import { createFile } from "@/api/files.js"
import { noWifi } from "@/axios/helper.js"
import { PipelineWorker } from "@/transfers/shared/base/PipelineWorker.js"
import { uploadFileStatus, uploadState } from "@/transfers/upload/constants.js"
import { workerExitReason } from "@/transfers/shared/constants.js"

const MAX_FILES_PER_BATCH = 20

export class BackendFileConsumer extends PipelineWorker {
   constructor({ backendFileQueue, uploadRuntime }) {
      super()

      this.backendFileQueue = backendFileQueue
      this.uploadRuntime = uploadRuntime

      this.finishedFiles = []
      this.failedFiles = []
      this._savePromise = null
      this._retryPromise = null
   }

   async run() {
      if (this._running) {
         console.warn("BackendFileConsumer is already running!")
         return workerExitReason.stopped
      }

      const signal = this._markStarted()
      let exitReason = workerExitReason.stopped

      try {
         while (!signal.aborted) {
            if (this._stopRequested) {
               await this.flushFiles(signal)
               exitReason = workerExitReason.stopped
               break
            }

            if (this.uploadRuntime.uploadState === uploadState.noInternet) {
               await this.uploadRuntime.waitUntilResumed(signal)
               continue
            }

            const file = await this.takeWithAbort(this.backendFileQueue, signal)

            if (!file) {
               await this.flushFiles(signal)
               exitReason = workerExitReason.inputEnded
               break
            }

            this.finishedFiles.push(file)
            await this.saveFilesIfNeeded(signal)
         }

         if (this._killed) {
            exitReason = workerExitReason.killed
         }

         return exitReason
      } catch (err) {
         exitReason = this._handleRunError(err)
         return exitReason
      } finally {
         this._markFinished(exitReason)
      }
   }

   async saveFilesIfNeeded(signal) {
      if (this._savePromise) {
         await this._savePromise
      }

      let totalSize = 0
      for (const file of this.finishedFiles) totalSize += file.size

      const shouldSave =
         this.finishedFiles.length >= MAX_FILES_PER_BATCH ||
         totalSize > 100 * 1024 * 1024

      if (shouldSave) {
         await this._saveCurrentFinishedFiles(signal)
      }
   }

   async flushFiles(signal) {
      while (this.finishedFiles.length && !this._killed && !signal?.aborted) {
         if (this.uploadRuntime.uploadState === uploadState.noInternet) {
            await this.uploadRuntime.waitUntilResumed(signal)
            continue
         }

         await this._saveCurrentFinishedFiles(signal)

      }
   }

   async _saveCurrentFinishedFiles(signal) {
      if (this._savePromise) {
         await this._savePromise
      }

      if (!this.finishedFiles.length) return

      this._throwIfAborted(signal)

      const batch = this.finishedFiles.splice(0, MAX_FILES_PER_BATCH)

      this._savePromise = this.saveFiles(batch)

      try {
         await this._savePromise
      } finally {
         this._savePromise = null
      }
   }

   saveFiles(files) {
      const resourcePasswords = {}

      for (const file of files) {
         const state = this.uploadRuntime.getFileState(file.frontend_id)
         const parentPassword = state.fileObj.parentPassword
         const lockFromId = state.fileObj.lockFrom

         if (parentPassword && lockFromId) {
            resourcePasswords[lockFromId] = parentPassword
         }
      }

      return createFile({ files, resourcePasswords }, { __displayErrorToast: false })
         .then(() => this.onBackendSave(files))
         .catch(err => this.onBackendSaveError(files, err))
   }

   onBackendSave(files) {
      for (const file of files) {
         this.uploadRuntime.finishExistingFile(file.frontend_id)
      }
   }

   onBackendSaveError(files, error) {
      console.log(error)
      if (noWifi(error)) {
         this.uploadRuntime.setUploadingState(uploadState.noInternet)
         for (const file of files) {
            this.backendFileQueue.put(file)
         }

      } else {
         for (const file of files) {
            const state = this.uploadRuntime.getFileState(file.frontend_id)
            state.setStatus(uploadFileStatus.saveFailed)
            state.setError(error?.response?.data)
            this.failedFiles.push(file)
         }
      }
   }

   async retryFailedFiles() {
      if (!this.failedFiles.length) return

      if (this._retryPromise) {
         await this._retryPromise
         return
      }

      this._retryPromise = (async () => {
         const batch = this.failedFiles
         this.failedFiles = []

         for (const file of batch) {
            const state = this.uploadRuntime.getFileState(file.frontend_id)
            state?.setStatus(uploadFileStatus.retrying)

            await new Promise(resolve => setTimeout(resolve, 250))
            await this.backendFileQueue.put(file)
         }
      })()

      try {
         await this._retryPromise
      } finally {
         this._retryPromise = null
      }
   }
}
