import axios from "axios"
import { fileUploadStatus, uploadState } from "@/utils/constants.js"
import { upload } from "@/upload/utils/uploadHelper.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { noWifi } from "@/axios/helper.js"
import i18n from "@/i18n/index.js"
import { useToast } from "vue-toastification"
import { encryptAttachment } from "@/upload/utils/encryption.js"
import { getUploader } from "@/upload/Uploader.js"

const toast = useToast()

export class DiscordUploadConsumer {
   constructor({ requestQueue, discordResponseQueue, uploadRuntime }) {
      this.uploadStore = useUploadStore()
      this.requestQueue = requestQueue
      this.discordResponseQueue = discordResponseQueue
      this.uploadRuntime = uploadRuntime
      this.abortRequestMap = new Map()
      this.running = false
      this.failedRequests = []
   }

   stop() {
      this.running = false
   }

   isRunning() {
      return this.running
   }

   async run() {
      if (this.running) {
         console.warn("DiscordUploadConsumer is already running!")
         return
      }
      this.running = true
      while (this.running) {
         if (this.uploadStore.state !== uploadState.uploading) {
            await this.waitUntilResumed()
         }
         const request = await this.requestQueue.take()
         if (!request) {
            console.warn("DiscordUploadConsumer breaking!")
            break
         }

         try {
            const discordResponse = await this.uploadSingleRequest(request)
            await this.discordResponseQueue.put({ request, discordResponse })
         } catch (error) {
            if (!error.handled) {
               this.onRequestUnhandledError(request, error)
            }
         }
      }
      this.running = false
   }

   async uploadSingleRequest(request) {
      const attachmentName = this.uploadStore.attachmentName

      if (this.uploadStore.state === uploadState.paused) {
         await this.waitUntilResumed()
      }
      try {
         const formData = await this.buildFormData(request, attachmentName)
         const controller = this.createAbortController(request)
         const config = this.buildDiscordAxiosConfig(request, controller.signal)

         await this.setStatusForRequest(request, fileUploadStatus.uploading)
         return await upload(formData, config)
      } catch (err) {
         this.handleUploadError(err, request)
      } finally {
         this.abortRequestMap.delete(request.id)
      }
   }

   async buildFormData(request, attachmentName) {
      const formData = new FormData()
      const attachmentJson = []

      for (let i = 0; i < request.attachments.length; i++) {
         const attachment = request.attachments[i]
         const fileState = this.uploadRuntime.getFileState(attachment.fileObj.frontendId)
         let encryptedBlob
         try {
            encryptedBlob = await encryptAttachment(attachment, fileState)
         } catch (err){
            if (err.name === "NotFoundError") {
               let err = new Error()
               err.name = "FileGone"
               err.frontendId = attachment.fileObj.frontendId
               throw err
            }
         }
         formData.append(`files[${i}]`, encryptedBlob, attachmentName)
         attachmentJson.push({ id: i, filename: attachmentName })
      }

      formData.append("json_payload", JSON.stringify({ attachments: attachmentJson }))
      return formData
   }

   buildDiscordAxiosConfig(request, abortSignal) {
      let totalBytesUploaded = 0

      return {
         onUploadProgress: progressEvent => {
            totalBytesUploaded = progressEvent.loaded
            if (!progressEvent.rate) progressEvent.rate = 0
            this.uploadRuntime.onUploadProgress(request, progressEvent)
         },

         onErrorCallback: error => {
            this.uploadRuntime.fixUploadTracking(request, totalBytesUploaded, error)
         },

         onRequestFinish: () => {
            let missing = request.totalSize - totalBytesUploaded
            if (missing < 0) missing = 0
            this.uploadRuntime.fixMissingBytesFromRequest(request, missing)
         },

         signal: abortSignal
      }
   }

   createAbortController(request) {
      const controller = new AbortController()
      this.abortRequestMap.set(request.id, controller)
      return controller
   }

   handleUploadError(err, request) {
      /**Handles axios error in DISCORD upload request*/
      if (axios.isCancel(err)) {
         this.requestQueue.put(request)
         err.handled = true
         throw err
      }
      if (noWifi(err)) {
         this.requestQueue.put(request)
         this.uploadRuntime.setUploadingState(uploadState.noInternet)
         err.handled = true
         throw err
      }

      if (err.name === "FileGone") {
         this.uploadRuntime.getFileState(err.frontendId).setStatus(fileUploadStatus.fileGoneInUpload)
         this.failedRequests.push(request)
         err.handled = true
         throw err
      }

      if (err.response?.data?.code === 10015) {
         toast.error(`${i18n.global.t("toasts.unknownWebhook", { "webhook": err.config.__webhook.name })}`, { timeout: null })
         getUploader().pauseAll()
      }

      request.attachments.forEach(att => {
         if (!noWifi(err)) {
            this.uploadRuntime.getFileState(att.fileObj.frontendId).setStatus(fileUploadStatus.uploadFailed)
            this.uploadRuntime.getFileState(att.fileObj.frontendId).setError(err.message)
         }
      })
      this.failedRequests.push(request)
      throw err
   }
   async setStatusForRequest(request, status) {
      for (let i = 0; i < request.attachments.length; i++) {
         const frontendId = request.attachments[i].fileObj.frontendId
         this.uploadRuntime.getFileState(frontendId).setStatus(status)
      }
   }

   abortAll() {
      for (const controller of this.abortRequestMap.values()) {
         controller.abort()
      }
      this.abortRequestMap.clear()
   }


   onRequestUnhandledError(request, error) {
      console.error(error)
      if (error && error.handled) return
      for (let attachment of request.attachments) {
         let frontendId = attachment.fileObj.frontendId
         const fileState = this.uploadRuntime.getFileState(frontendId)
         if (fileState.status === fileUploadStatus.uploadFailed || fileState.status === fileUploadStatus.saveFailed) return
         fileState.setStatus(fileUploadStatus.errorOccurred)
         fileState.setError(error)
      }
   }

   async retryGoneFile(frontendId) {
      if (!this.failedRequests.length) return

      const toRetry = []
      const remaining = []

      for (const request of this.failedRequests) {
         const hasFile = request.attachments.some(att => att.fileObj.frontendId === frontendId)

         if (hasFile) {
            toRetry.push(request)
         } else {
            remaining.push(request)
         }
      }

      if (!toRetry.length) {
         return
      }

      this.failedRequests.push(...remaining)

      const fileState = this.uploadRuntime.getFileState(frontendId)
      fileState.setStatus(fileUploadStatus.retrying)


      for (const request of toRetry) {
         await this.requestQueue.put(request)
      }
   }
   async retryFailedRequests() {
      const batch = this.failedRequests
      this.failedRequests = []

      for (const request of batch) {
         for (const attachment of request.attachments) {
            const frontendId = attachment.fileObj.frontendId
            const fileState = this.uploadRuntime.getFileState(frontendId)
            fileState.setStatus(fileUploadStatus.retrying)
         }
         await this.requestQueue.put(request)
      }
   }

   async waitUntilResumed() {
      await new Promise(resolve => {
         const unsub = this.uploadStore.$subscribe((_m, state) => {
            if (state.state === uploadState.uploading) {
               unsub()
               resolve()
            }
         })
      })
   }
}
