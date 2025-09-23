import { defineStore } from "pinia"
import { attachmentType, fileUploadStatus, uploadState } from "@/utils/constants.js"
import { FileStateHolder } from "@/upload/FileStateHolder.js"
import { getUploader } from "@/upload/Uploader.js"

export const useUploadStore = defineStore("upload", {
   state: () => ({
      queue: [],
      state: uploadState.idle,
      benchedRequests: [],

      //UI
      uploadSpeedMap: new Map(),
      progressMap: new Map(),
      fileState: [],
      eta: Infinity
   }),

   getters: {
      isAllUploadsFinished() {
         return this.fileState.every(file => file.isFullyUploaded() && this.queue.length === 0)
      },
      uploadSpeed() {
         let uploadSpeed = Array.from(this.uploadSpeedMap.values()).reduce((sum, value) => sum + value, 0)
         if (isNaN(uploadSpeed)) {
            return 0
         }

         return uploadSpeed
      },
      filesInUpload() {
         return this.fileState
            .filter(f => f.status !== fileUploadStatus.waitingForSave)  // exclude failed files
            .sort((a, b) => b.progress - a.progress)
            .slice(0, 10)
      },
      remainingBytes() {
         let totalQueueSize = this.queue.reduce((total, item) => total + item.fileObj.size, 0)

         let remainingUploadSize = this.fileState.reduce((total, item) => {

            let uploadedSize = item.fileObj.size * (item.fileObj.progress / 100)
            let remainingSize = item.fileObj.size - uploadedSize
            return total + remainingSize
         }, 0)

         return totalQueueSize + remainingUploadSize
      },
      filesInUploadCount() {
         return this.queue.length + this.fileState.length

      },
      progress() {
         return 0
      }

   },

   actions: {
      async startUpload(type, folderContext, filesList) {
         this.state = uploadState.uploading
         await getUploader().startUpload(type, folderContext, filesList)
      },

      getFileFromQueue() {
         if (this.queue.length === 0) {
            console.warn("getFileFromQueue is empty, yet it was called idk why")
            return
         }

         let file = this.queue.shift() //get and remove the file
         this.fileState.push(new FileStateHolder(file.fileObj))

         return file
      },
      setState(state) {
        this.state = state
      },
      setStatus(frontendId, status) {
         let file = this.fileState.find(item => item.frontendId === frontendId)
         if (file) {
            file.status = status
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the fileState.`)
         }
      },

      markFileUploaded(frontendId) {
         this.setStatus(frontendId, fileUploadStatus.uploaded)
         setTimeout(() => {
            let file = this.fileState.find(item => item.frontendId === frontendId)
            if (!file || file.status !== fileUploadStatus.uploaded) return
            this.setStatus(frontendId, fileUploadStatus.waitingForSave)
         }, 1500)
      },
      setProgress(frontendId, percentage) {
         let file = this.fileState.find(item => item.frontendId === frontendId)
         if (file) {
            file.progress = percentage
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the fileState.`)
         }
      },
      fixUploadTracking(request, bytesUploaded) {
         /** This fixes the progress ui tracking*/
         this.uploadSpeedMap.delete(request.id)

         for (let attachment of request.attachments) {
            let frontendId = attachment.fileObj.frontendId
            if (this.progressMap.has(frontendId)) {
               let currentValue = this.progressMap.get(frontendId)
               let newValue = Math.max(0, currentValue - bytesUploaded)
               this.progressMap.set(frontendId, newValue)
            }
         }
      },
      onUploadProgress(request, progressEvent) {
         this.uploadSpeedMap.set(request.id, progressEvent.rate)
         getUploader().estimator.updateSpeed(this.uploadSpeed)
         this.eta = getUploader().estimator.estimateRemainingTime(this.remainingBytes)

         let uploadedSoFar = progressEvent.bytes
         let totalSize = request.totalSize
         for (let attachment of request.attachments) {
            let fileObj = attachment.fileObj
            let frontendId = fileObj.frontendId

            if (attachment.type === attachmentType.file) {

               let attachmentSize = attachment.rawBlob.size
               let estimatedUploaded = Math.floor((attachmentSize / totalSize) * uploadedSoFar)
               // Track uploaded bytes per attachment
               if (this.progressMap.has(frontendId)) {
                  let currentValue = this.progressMap.get(frontendId)
                  this.progressMap.set(frontendId, currentValue + estimatedUploaded)
               } else {
                  this.progressMap.set(frontendId, estimatedUploaded)
               }

               // Convert to percentage
               let totalLoadedBytes = this.progressMap.get(frontendId)
               let percentage = Math.floor((totalLoadedBytes / fileObj.size) * 100)
               if (percentage > 100) {
                  console.warn(`Percentage overflow(${percentage}%) in upload for file: ${fileObj.name}, size=${fileObj.size}, reportedSize=${totalLoadedBytes}`)
                  percentage = 100
               }
               this.setProgress(frontendId, percentage)
            }
         }
      },

      setTotalChunks(frontendId, totalChunks) {
         const fileObj = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileObj) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
            return
         }
         fileObj.setTotalChunks(totalChunks)
      },

      incrementChunk(frontendId) {
         const fileObj = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileObj) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
            return
         }
         fileObj.incrementChunk()
      },

      markThumbnailRequired(frontendId) {
         const fileObj = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileObj) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
            return
         }
         fileObj.markThumbnailRequired()
      },

      markVideoMetadataRequired(frontendId) {
         const fileObj = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileObj) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
            return
         }
         fileObj.markVideoMetadataRequired()
      },

      markThumbnailUploaded(frontendId) {
         const fileObj = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileObj) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
            return
         }
         fileObj.markThumbnailUploaded()
      },

      markVideoMetadataExtracted(frontendId) {
         const fileObj = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileObj) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
            return
         }
         fileObj.markVideoMetadataExtracted()
      },

      isFileUploaded(frontendId) {
         const fileObj = this.fileState.find(f => f.frontendId === frontendId)
         if (!fileObj) {
            console.warn(`File with frontendId ${frontendId} not found in fileState`)
            return
         }
         return fileObj.isFullyUploaded()
      },

      addBenchedRequest(request) {
         this.benchedRequests.push(request)
      },

      finishRequest(request) {
         this.uploadSpeedMap.delete(request.id)
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

      retryGoneFile(frontendId) {

      },

      dismissGoneFile(frontendId) {
         //todo??
         let index = this.fileState.findIndex(file => file.frontendId === frontendId)
         if (index !== -1) {
            this.fileState.splice(index, 1)
         } else {
            console.warn("Failed to find file: " + frontendId + " in fileState")
         }
      },

      retryAll() {
         this.resumeAll()
      },

      pauseAll() {
         this.state = uploadState.paused
         getUploader().pauseAllFiles()

      },
      resumeAll() {
         this.state = uploadState.uploading
         getUploader().processUploads()
      },

   }
})

const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}