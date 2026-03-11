import { fileUploadStatus, uploadState } from "@/utils/constants.js"
import { createFile } from "@/api/files.js"
import { showToast } from "@/utils/common.js"
import { getUploader } from "@/upload/Uploader.js"
import { noWifi } from "@/axios/helper.js"

const SMALL_FILE_LIMIT = 0.1 * 1024 * 1024
const NORMAL_FILE_COUNT = 20
const SMALL_FILE_COUNT = 99

export class BackendFileConsumer {
   constructor({ backendFileQueue, uploadRuntime }) {
      this.backendFileQueue = backendFileQueue
      this.uploadRuntime = uploadRuntime

      this.finishedFiles = []
      this.failedFiles = []
      this.databaseErrors = 0
      this.running = false
   }

   stop() {
      this.running = false
   }

   isRunning() {
      return this.running
   }

   async run() {
      if (this.running) {
         console.warn("BackendFileConsumer is already running!")
         return
      }
      this.running = true
      while (this.running) {
         if (this.uploadRuntime.uploadState === uploadState.noInternet) {
            await this.uploadRuntime.waitUntilResumed()
         }
         const file = await this.backendFileQueue.take()
         if (!file) break

         this.finishedFiles.push(file)
         await this.saveFilesIfNeeded()
      }
      this.running = false
   }

   shouldSaveFiles() {
      for (const file of this.uploadRuntime.fileStates.values()) {
         if (file.isErrorStatus()) {
            continue
         }
         if (!file.isFullyUploaded()) return false
      }
      return true
   }

   async saveFilesIfNeeded() {
      let totalSize = 0
      for (const file of this.finishedFiles) totalSize += file.size

      const allFilesAreSmall = this.finishedFiles.every(
         file => file.size < SMALL_FILE_LIMIT
      )

      const fileCountThreshold = allFilesAreSmall
         ? SMALL_FILE_COUNT
         : NORMAL_FILE_COUNT

      if (
         this.finishedFiles.length > fileCountThreshold ||
         totalSize > 100 * 1024 * 1024 ||
         this.shouldSaveFiles() ||
         this.uploadRuntime.isUploadFullyFinished()
      ) {
         const batch = this.finishedFiles
         this.finishedFiles = []
         this.saveFiles(batch)
      }
   }

   saveFiles(files) {
      const resourcePasswords = {}

      for (const file of files) {
         let state = this.uploadRuntime.getFileState(file.frontend_id)
         let parentPassword = state.fileObj.parentPassword
         let lockFromId = state.fileObj.lockFrom

         if (parentPassword && lockFromId) {
            resourcePasswords[lockFromId] = parentPassword
         }
      }

      createFile({ files, resourcePasswords }, { __displayErrorToast: false })
         .then(() => this.onBackendSave(files))
         .catch(err => this.onBackendSaveError(files, err))
   }


   onBackendSave(files) {
      for (const file of files) {
         this.uploadRuntime.markFileSaved(file.frontend_id)
      }
      this.databaseErrors = Math.max(this.databaseErrors - 1, 0)
   }

   onBackendSaveError(files, error) {
      if (noWifi(error)) {
         this.uploadRuntime.setUploadingState(uploadState.noInternet)
         for (const file of files) {
            this.backendFileQueue.put(file)
         }

      } else {
         for (const file of files) {
            const state = this.uploadRuntime.getFileState(file.frontend_id)
            state.setStatus(fileUploadStatus.saveFailed)
            state.setError(error?.response?.data)
            this.failedFiles.push(file)
         }
      }

      if (error.response?.status >= 500) this.databaseErrors++

      if (this.databaseErrors > 2) {
         getUploader().pauseAll()
         showToast("error", "toasts.databaseIsLockedUploadPaused")
         this.databaseErrors = 0
      }
   }

   async retryFailedFiles() {
      if (!this.failedFiles.length) {
         return
      }

      const batch = this.failedFiles
      this.failedFiles = []

      for (const file of batch) {
         const state = this.uploadRuntime.getFileState(file.frontend_id)
         if (state) state.setStatus(fileUploadStatus.retrying)

         await new Promise(resolve => setTimeout(resolve, 500))
         this.backendFileQueue.put(file)
      }
   }
}
