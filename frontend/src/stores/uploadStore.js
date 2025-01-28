import { defineStore } from "pinia"
import { prepareRequests, uploadRequest } from "@/utils/upload.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, uploadStatus } from "@/utils/constants.js"
import buttons from "@/utils/buttons.js"
import { useToast } from "vue-toastification"
import { Uploader } from "@/utils/Uploader.js"
import { canUpload } from "@/api/user.js"
import { detectType } from "@/utils/uploadHelper.js"
import { createFile } from "@/api/files.js"
import i18n from "@/i18n/index.js"

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
      axiosRequests: new Map(),
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

      finished: false
   }),

   getters: {
      isUploadFinished() {
        if (this.filesUploading.length > 20) {
           return false
        }
        let flag = true
        for (let file of this.filesUploading) {
           if (file.status !== uploadStatus.uploaded || file.status !== uploadStatus.failed) {
              flag = false
           }
        }
        return this.queue.length === 0 && !this.requestGenerator && this.concurrentRequests === 0 // && flag
      },
      uploadSpeed() {
         let uploadSpeed = Array.from(this.uploadSpeedMap.values()).reduce((sum, value) => sum + value, 0)
         if (isNaN(uploadSpeed)) {
            return 0
         }

         return uploadSpeed
      },
      filesInUpload() {

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
         let queue = this.queue.length
         let filesUploading = this.filesUploading.length

         return queue + filesUploading

      },
      progress() {
         return 50
      }

   },

   actions: {
      async startUpload(type, folderContext, filesList) {

         let res = await canUpload(folderContext)
         if (!res.can_upload) {
            toast.error(i18n.global.t('errors.notAllowedToUpload'))
            return
         }
         console.log("folderContext")
         console.log(folderContext)

         this.uploader.processNewFiles(type, folderContext, filesList, res.lockFrom)
         //todo NotOptimizedForSmallFiles

      },

      async processUploads() {
         console.log("called proccess Uploads")
         const mainStore = useMainStore()
         let canProcess = this.concurrentRequests < mainStore.settings.concurrentUploadRequests

         if (!canProcess) return

         if (!this.requestGenerator) {
            this.requestGenerator = prepareRequests()
            this.finished = false

         }
         let generated = await this.requestGenerator.next()


         if (generated.done) {
            console.info("The request generator is finished.")
            this.requestGenerator = null
            this.finished = true
            return
         }
         let request = generated.value
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
         fileObj.status = uploadStatus.preparing
         fileObj.progress = 0

         this.filesUploading.push(fileObj)

         this.queue.shift() // Remove the file from the queue
         return file
      },
      setStatus(frontendId, status) {
         let file = this.filesUploading.find(item => item.frontendId === frontendId)
         if (file) {
            file.status = status
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the queue.`)
         }
      },
      finishFileUpload(frontendId) {
         this.setStatus(frontendId, uploadStatus.uploaded)
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
      onUploadProgress(request, progressEvent) {
         this.isInternet = true

         this.uploadSpeedMap.set(request.id, progressEvent.rate)
         this.uploader.estimator.updateSpeed(this.uploadSpeed)
         this.eta = this.uploader.estimator.estimateRemainingTime(this.remainingBytes)

         for (let attachment of request.attachments) {
            let frontendId = attachment.fileObj.frontendId

            if (attachment.type === attachmentType.entireFile) {
               let progress = progressEvent.progress
               let percentage = Math.floor(progress * 100)
               this.setProgress(frontendId, percentage)
            } else if (attachment.type === attachmentType.chunked) {
               let loadedBytes = progressEvent.bytes

               if (this.progressMap.has(frontendId)) {
                  // Key exists, update the value
                  let currentValue = this.progressMap.get(frontendId)
                  this.progressMap.set(frontendId, currentValue + loadedBytes)
               } else {
                  // Key does not exist, create it and set to 0
                  this.progressMap.set(frontendId, 0)
               }
               let totalLoadedBytes = this.progressMap.get(frontendId)
               let percentage = Math.floor(totalLoadedBytes / attachment.fileObj.size * 100)
               this.setProgress(attachment.fileObj.frontendId, percentage)
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
      finishUpload() {
         this.requestGenerator = null
         this.queue = []
         this.filesUploading = []
         this.pausedFiles = []
         this.axiosRequests = new Map()
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
         let abortController = this.axiosRequests.get("blabla")
         if (abortController) {
            abortController.abort()
            console.log("Upload request canceled by user.")
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

      //experimental
      fillAttachmentInfo(attachment, request, discordResponse, discordAttachment) {
         let fileObj = attachment.fileObj

         if (!this.backendState.has(fileObj.frontendId)) {

            let file_data = {
               "name": fileObj.name,
               "parent_id": fileObj.folderId,
               "mimetype": detectType(fileObj),
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
         if (attachment.type === attachmentType.chunked || attachment.type === attachmentType.entireFile) {
            let attachment_data = {
               "fragment_sequence": attachment.fragmentSequence,
               "fragment_size": attachment.rawBlob.size,
               "message_id": discordResponse.data.id,
               "attachment_id": discordAttachment.id,
               "webhook": request.webhook.discord_id
            }
            state.attachments.push(attachment_data)
         }
         else if (attachment.type === attachmentType.thumbnail) {
            state.thumbnail = {
               "size": attachment.rawBlob.size,
               "message_id": discordResponse.data.id,
               "attachment_id": discordAttachment.id,
               "iv": attachment.iv,
               "key": attachment.key,
               "webhook": request.webhook.discord_id
            }
         }
         this.backendState.set(fileObj.frontendId, state)

         if (state.attachments.length === fileObj.totalChunks && ((fileObj.thumbnail && state.thumbnail) || !fileObj.thumbnail)) {
            this.finishedFiles.push(state)
            this.finishFileUpload(fileObj.frontendId)
         }
         if (this.finishedFiles.length > 10 || (this.isUploadFinished && this.finishedFiles.length > 0)) {
            console.log("fileObj.password")
            console.log(fileObj.parentPassword)
            createFile({"files": this.finishedFiles}, fileObj.parentPassword)
            this.finishedFiles = []
         }
         
      }


   }
})
const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}