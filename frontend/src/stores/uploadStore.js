import { defineStore } from "pinia"
import { prepareRequests, uploadRequest } from "@/utils/upload.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, fileUploadStatus, uploadState } from "@/utils/constants.js"
import buttons from "@/utils/buttons.js"
import { useToast } from "vue-toastification"
import { Uploader } from "@/utils/Uploader.js"
import { canUpload } from "@/api/user.js"
import { createFile } from "@/api/files.js"
import i18n from "@/i18n/index.js"
import { v4 as uuidv4 } from "uuid"

const toast = useToast()

export const useUploadStore = defineStore("upload2", {
   state: () => ({
      queue: [],
      concurrentRequests: 0,
      filesUploading: [],

      createdFolders: new Map(),

      //UI
      uploadSpeedMap: new Map(),
      progressMap: new Map(),

      //never finished
      axiosCancelMap: new Map(),
      pausedFiles: [],

      //simply dumb
      requestGenerator: null,
      uploader: new Uploader(),

      eta: Infinity,
      attachmentName: "",
      webhooks: [],

      //experimental
      backendState: new Map(),
      finishedFiles: [],
      finished: false,

      pausedRequests: [],

      state: uploadState.idle

   }),

   getters: {
      isUploadFinished() {
         return this.queue.length === 0 && this.uploadSpeedMap.size <= 1 && this.concurrentRequests === 0 // && flag
      },
      uploadSpeed() {
         let uploadSpeed = Array.from(this.uploadSpeedMap.values()).reduce((sum, value) => sum + value, 0)
         if (isNaN(uploadSpeed)) {
            return 0
         }

         return uploadSpeed
      },
      filesInUpload() {
         // return [{"name": "name", "status": "uploading"}]
         return this.filesUploading
            .sort((a, b) => b.progress - a.progress)
            .slice(0, 10)
      },
      remainingBytes() {
         let totalQueueSize = this.queue.reduce((total, item) => total + item.fileObj.size, 0)

         let remainingUploadSize = this.filesUploading.reduce((total, item) => {

            let uploadedSize = item.size * (item.progress / 100)
            let remainingSize = item.size - uploadedSize
            return total + remainingSize
         }, 0)

         return totalQueueSize + remainingUploadSize
      },
      filesInUploadCount() {
         // return 1
         let queue = this.queue.length
         let filesUploading = this.filesUploading.length

         return queue + filesUploading

      },
      progress() {
         return 0
      }

   },

   actions: {
      async startUpload(type, folderContext, filesList) {
         // window.addEventListener("beforeunload", beforeUnload)

         this.state = uploadState.uploading

         let res = await canUpload(folderContext)
         if (!res.can_upload) {
            toast.error(i18n.global.t("errors.notAllowedToUpload"))
            return
         }

         this.uploader.processNewFiles(type, folderContext, filesList, res.lockFrom)
         //todo NotOptimizedForSmallFiles

      },

      async processUploads() {
         const mainStore = useMainStore()
         let canProcess = this.concurrentRequests < mainStore.settings.concurrentUploadRequests &&
            (this.state === uploadState.uploading || this.state === uploadState.idle)

         if (!canProcess) return

         if (!this.requestGenerator) {
            this.requestGenerator = prepareRequests()
            this.finished = false

         }
         let request
         if (this.pausedRequests.length > 0) {
            request = this.pausedRequests[0]
            this.pausedRequests.shift() // Remove the request
         } else {
            let generated = await this.requestGenerator.next()
            if (generated.done) {
               console.info("The request generator is finished.")
               this.requestGenerator = null
               this.finished = true
               return
            }
            request = generated.value
            request.id = uuidv4()
         }

         this.concurrentRequests++

         uploadRequest(request)

         this.processUploads()

      },
      getFileFromQueue() {

         if (this.queue.length === 0) {
            console.warn("getFileFromQueue is empty, yet it was called idk why")
            return
         }

         let file = this.queue[0]

         let fileObj = file.fileObj
         fileObj.status = fileUploadStatus.preparing
         fileObj.progress = 0

         this.filesUploading.push(fileObj)

         this.queue.shift() // Remove the file from the queue
         return file
      },
      setStatus(frontendId, status) {
         let file = this.filesUploading.find(item => item.frontendId === frontendId)
         if (file) {
            if (status === fileUploadStatus.uploaded && this.state === uploadState.paused) return
            file.status = status
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the queue.`)
         }
      },
      finishFileUpload(frontendId) {
         this.setStatus(frontendId, fileUploadStatus.uploaded)
         setTimeout(() => {
            //remove file from filesUploading
            this.filesUploading = this.filesUploading.filter(item => item.frontendId !== frontendId)

         }, 2000)

      },
      setProgress(frontendId, percentage) {
         let file = this.filesUploading.find(item => item.frontendId === frontendId)
         if (file) {
            file.progress = percentage
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the queue.`)
         }
      },
      onUploadError(request, bytesUploaded) {
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
         this.isInternet = true
         this.uploadSpeedMap.set(request.id, progressEvent.rate)
         this.uploader.estimator.updateSpeed(this.uploadSpeed)
         this.eta = this.uploader.estimator.estimateRemainingTime(this.remainingBytes)

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
      finishRequest(requestId) {
         // this.concurrentRequests--
         this.uploadSpeedMap.delete(requestId)
         //this.etaMap.delete(requestId)

         this.processUploads()
      },
      decrementRequests() {
         this.concurrentRequests--
      },
      abortAll() {

      },
      abortFile(frontendId) {

      },
      forceUnstuck() {
         //todo
         this.concurrentRequests = 0
         this.uploadSpeedMap = new Map()
         this.progressMap = new Map()
         this.filesUploading = []
         this.processUploads()
      },
      pauseAll() {
         this.state = uploadState.paused
         this.filesUploading.forEach(file => file.status = fileUploadStatus.paused)
         for (let sourceList of this.axiosCancelMap.values()) {
            for (let source of sourceList) {
               source.cancel()
            }
         }
      },
      resumeAll() {
         this.state = uploadState.uploading
         this.processUploads()

      },
      addPausedRequest(request) {
         const requestExists = this.pausedRequests.some(req => req.id === request.id)

         if (!requestExists) {
            this.pausedRequests.push(request) // Add the request if it doesn't exist
         } else {
            console.warn("Request with this ID already exists.")
         }
      },
      addCancelToken(frontendId, cancelToken) {
         if (!this.axiosCancelMap.has(frontendId)) {
            this.axiosCancelMap.set(frontendId, [])
         }
         console.log(cancelToken)
         this.axiosCancelMap.get(frontendId).push(cancelToken)
      },
      finishUpload() {
         this.requestGenerator = null
         this.queue = []
         this.filesUploading = []
         this.pausedRequests = []
         this.axiosCancelMap = new Map()
         this.createdFolders = new Map()
         this.uploadSpeedMap = new Map()
         this.progressMap = new Map()

         window.removeEventListener("beforeunload", beforeUnload)
         buttons.success("upload")

      },
      resumeFile(frontendId) {
         toast.info("errors.notImplemented")

      },
      pauseFile(frontendId) {
         toast.info("errors.notImplemented")
      },
      cancelFile(frontendId) {

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

      //experimental
      fillAttachmentInfo(attachment, request, discordResponse, discordAttachment) {
         let fileObj = attachment.fileObj
         console.log(discordResponse)
         if (!this.backendState.has(fileObj.frontendId)) {

            let file_data = {
               "name": fileObj.name,
               "parent_id": fileObj.folderId,
               "mimetype": fileObj.type,
               "extension": fileObj.extension,
               "size": fileObj.size,
               "frontend_id": fileObj.frontendId,
               "encryption_method": parseInt(fileObj.encryptionMethod),
               "created_at": fileObj.createdAt,
               "duration": fileObj.duration,
               "iv": fileObj.iv,
               "key": fileObj.key,
               "attachments": []
            }
            this.backendState.set(fileObj.frontendId, file_data)
         }
         let state = this.backendState.get(fileObj.frontendId)
         if (attachment.type === attachmentType.file) {
            let attachment_data = {
               "fragment_sequence": attachment.fragmentSequence,
               "fragment_size": attachment.rawBlob.size,
               "message_id": discordResponse.data.id,
               "attachment_id": discordAttachment.id,
               "message_author_id": discordResponse.data.author.id,
               "offset": attachment.offset
            }
            state.attachments.push(attachment_data)
         } else if (attachment.type === attachmentType.thumbnail) {
            state.thumbnail = {
               "size": attachment.rawBlob.size,
               "message_id": discordResponse.data.id,
               "attachment_id": discordAttachment.id,
               "iv": attachment.iv,
               "key": attachment.key,
               "message_author_id": discordResponse.data.author.id,
            }
         }
         this.backendState.set(fileObj.frontendId, state)
         if (state.attachments.length === fileObj.totalChunks && ((fileObj.thumbnail && state.thumbnail) || !fileObj.thumbnail)) {
            this.finishedFiles.push(state)
            this.finishFileUpload(fileObj.frontendId)
         }
         let totalSize = 0
         for (let finishedFile of this.finishedFiles) {
            totalSize += finishedFile.size
         }
         if (this.finishedFiles.length > 20 || totalSize > 100 * 1024 * 1024 || (this.isUploadFinished && this.finishedFiles.length > 0)) {
            createFile({ "files": this.finishedFiles }, fileObj.parentPassword)
            this.finishedFiles = []
         }

      }


   }
})
const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}