import { defineStore } from "pinia"
import { attachmentType, fileUploadStatus, uploadState } from "@/utils/constants.js"
import { FileStateHolder } from "@/upload/FileStateHolder.js"
import { getUploader } from "@/upload/Uploader.js"
import { useToast } from "vue-toastification"
import i18n from "@/i18n/index.js"
import { checkFilesSizes, isErrorStatus } from "@/upload/uploadHelper.js"
import { useMainStore } from "@/stores/mainStore.js"
//todo add all to cleanup
export const useUploadStore = defineStore("upload", {
   state: () => ({
      queue: [],
      state: uploadState.idle,
      pausedRequests: [],
      failedRequests: [],
      erroredRequests: [],
      goneFiles: [],

      currentRequests: 0,

      //UI
      allBytesToUpload: 0,
      allBytesUploaded: 0,
      uploadSpeedMap: new Map(),
      fileState: [],
      eta: Infinity
   }),

   getters: {
      areAllUploadsFinished() {
         return this.fileState.every(file => file.isFullyUploaded() && this.queue.length === 0)
      },
      isAllFinished() {
         return this.fileState.length === 0 && this.queue.length === 0
      },

      uploadSpeed() {
         const uploadSpeed = Array.from(this.uploadSpeedMap.values()).reduce((sum, value) => sum + value, 0)
         if (isNaN(uploadSpeed)) {
            return 0
         }
         return uploadSpeed
      },
      filesInUpload() {
         return []
         const N = 10 // maximum files to display

         if (this.fileState.length < 5) {
            // shallow copy all files if fewer than 5
            return [...this.fileState]
         }

         // Filter first: remove waitingForSave files
         const filtered = this.fileState.filter(f => f.status !== fileUploadStatus.waitingForSave)

         // Slice top N after sorting by progress
         // only take top N files
         return filtered
            .slice() // make a shallow copy to avoid mutating original
            .sort((a, b) => b.progress - a.progress) // sort descending by progress
            .slice(0, N)
      },
      remainingBytes() {
         let totalQueueSize = this.queue.reduce((total, item) => total + item.fileObj.size, 0)

         let remainingUploadSize = this.fileState.reduce((total, item) => {

            const uploadedSize = item.fileObj.size * (item.progress / 100)
            const remainingSize = item.fileObj.size - uploadedSize
            return total + remainingSize
         }, 0)

         return totalQueueSize + remainingUploadSize
      },
      filesInUploadCount() {
         return this.queue.length + this.fileState.length
      },
      progress() {
         return (this.allBytesUploaded / this.allBytesToUpload) * 100
      }

   },

   actions: {
      async startUpload(type, folderContext, filesList) {
         if (await checkFilesSizes(filesList)) {
            useMainStore().showHover({
               prompt: "notOptimizedForSmallFiles",
               confirm: () => {
                  this.state = uploadState.uploading
                  getUploader().startUpload(type, folderContext, filesList)
               }
            })
         } else {
            this.state = uploadState.uploading
            await getUploader().startUpload(type, folderContext, filesList)
         }

      },

      getFileFromQueue() {
         if (this.queue.length === 0) {
            console.warn("getFileFromQueue is empty, yet it was called idk why")
            return
         }

         const file = this.queue.shift() // get and remove the file

         // Only add to fileState if it doesn't already exist
         const exists = this.fileState.some(f => f.frontendId === file.fileObj.frontendId)
         if (!exists) {
            this.fileState.push(new FileStateHolder(file))
         }

         return file
      },
      setState(state) {
         this.state = state
      },
      setStatus(frontendId, status) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return
         /**We must filter statuses*/
         if (isErrorStatus(fileState.status) && status === fileUploadStatus.uploading) return
         // if (fileState.status === fileUploadStatus.paused && status === fileUploadStatus.uploading) return
         fileState.error = null
         fileState.status = status
      },

      setError(frontendId, error) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         fileState.error = error
      },

      markFileUploaded(frontendId) {
         this.setStatus(frontendId, fileUploadStatus.uploaded)
         setTimeout(() => {
            let file = this.fileState.find(item => item.frontendId === frontendId)
            if (!file || file.status !== fileUploadStatus.uploaded) return
            this.setStatus(frontendId, fileUploadStatus.waitingForSave)
         }, 1500)
      },

      fixUploadTracking(request, bytesUploaded) {
         /** This fixes the progress ui tracking */
         this.uploadSpeedMap.delete(request.id)
         this.allBytesUploaded -= bytesUploaded

         for (let attachment of request.attachments) {
            let fileState = this.getFileState(attachment.fileObj.frontendId)
            this.setStatus(fileState.frontendId, fileUploadStatus.retrying)
            fileState.setUploadedBytes(Math.max(0, fileState.uploadedBytes - bytesUploaded))
         }
      },
      onUploadProgress(request, progressEvent) {
         this.allBytesUploaded += progressEvent.bytes
         this.uploadSpeedMap.set(request.id, progressEvent.rate)
         getUploader().estimator.updateSpeed(this.uploadSpeed)
         this.eta = getUploader().estimator.estimateRemainingTime(this.remainingBytes)

         const uploadedSoFar = progressEvent.bytes
         const totalSize = request.totalSize

         for (let attachment of request.attachments) {
            const fileObj = attachment.fileObj
            const fileState = this.getFileState(fileObj.frontendId)

            if (attachment.type === attachmentType.file) {
               const attachmentSize = attachment.rawBlob.size
               const estimatedUploaded = Math.floor((attachmentSize / totalSize) * uploadedSoFar)

               fileState.updateUploadedBytes(estimatedUploaded)

               let percentage = fileState.progress
               if (percentage > 100) {
                  console.warn(`Percentage overflow(${percentage}%) in upload for file: ${fileObj.name}, size=${fileObj.size}, reportedSize=${fileState.uploadedBytes}`)
                  percentage = 100
                  fileState.progress = percentage
               }

            }
         }
      },

      setTotalChunks(frontendId, totalChunks) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return
         fileState.setTotalChunks(totalChunks)
      },
      onNewFileChunk(frontendId, offset, extractedChunks) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         fileState.offset = offset
         fileState.extractedChunks = extractedChunks

      },

      incrementChunk(frontendId) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         fileState.incrementChunk()
      },

      markThumbnailExtracted(frontendId) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         fileState.markThumbnailExtracted()
      },

      markVideoMetadataRequired(frontendId) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         fileState.markVideoMetadataRequired()
      },

      markThumbnailUploaded(frontendId) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         fileState.markThumbnailUploaded()
      },

      markVideoMetadataExtracted(frontendId) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         fileState.markVideoMetadataExtracted()
      },

      isFileUploaded(frontendId) {
         const fileState = this.getFileState(frontendId)
         if (!fileState) return

         return fileState.isFullyUploaded()
      },

      addPausedRequest(request) {
         this.pausedRequests.push(request)
      },
      addFailedRequest(request) {
         this.failedRequests.push(request)
      },
      markRequestFinished(request) {
         // this.allBytesUploaded += request.totalSize
         this.uploadSpeedMap.delete(request.id)
      },

      getFileState(frontendId) {
         let fileState = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileState) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
         }
         return fileState
      },

      markFileSaved(frontendId) {
         let index = this.fileState.findIndex(f => f.frontendId === frontendId)
         if (index !== -1) {
            this.fileState.splice(index, 1)
         } else {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
         }
      },

      addToWebhooks(webhook) {
         this.webhooks.push(webhook)
      },
      removeWebhook(discord_id) {
         this.webhooks = this.webhooks.filter(webhook => webhook.discord_id !== discord_id)
      },
      setWebhooks(value) {
         this.webhooks = value
      },
      setAttachmentName(value) {
         this.attachmentName = value
      },
      setFileExtensions(value) {
         this.fileExtensions = value
      },

      retryFailSaveFile(frontendId) {
         getUploader().reSaveFile(frontendId)
      },

      retryGoneFile(frontendId) {
         let state = this.getFileState(frontendId)
         if (!state) return
         this.setStatus(frontendId, fileUploadStatus.retrying)
         let newFile = { systemFile: state.systemFile, fileObj: state.fileObj }
         this.queue.unshift(newFile)
         getUploader().processUploads()
      },

      dismissFile(frontendId) {
         let index = this.fileState.findIndex(file => file.frontendId === frontendId)
         if (index !== -1) {
            this.fileState.splice(index, 1)
         } else {
            console.warn("Failed to find file: " + frontendId + " in fileState")
         }

         this.onUploadFinish()
      },

      retryAll() {
         this.resumeAll()
      },

      pauseAll() {
         this.state = uploadState.paused
         getUploader().discordUploader.pauseAllRequests()

      },
      resumeAll() {
         this.state = uploadState.uploading
         getUploader().processUploads()
      },

      onUploadFinish() {
         if (this.isAllFinished) {
            this.state = uploadState.idle
            this.queue = []
            this.pausedRequests = []
            this.failedRequests = []
            this.erroredRequests = []
            this.goneFiles = []
            this.currentRequests = 0

            //UI
            this.uploadSpeedMap = new Map()
            this.fileState = []
            this.eta = Infinity
            this.allBytesToUpload = 0
            this.allBytesUploaded = 0

            getUploader().cleanup()
            useToast().success(i18n.global.t("toasts.uploadFinished"))
         }

      }

   }
})
