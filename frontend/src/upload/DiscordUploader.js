import axios from "axios"
import { fileUploadStatus, uploadState } from "@/utils/constants.js"
import { upload } from "@/upload/uploadHelper.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { noWifi } from "@/axios/helper.js"
import { encryptAttachment } from "@/utils/encryption.js"
import i18n from "@/i18n/index.js"
import { useToast } from "vue-toastification"

const toast = useToast()

export class DiscordUploader {
   constructor() {
      this.uploadStore = useUploadStore()
      this.abortRequestMap = new Map()
      this.failedRequests = []
   }


   async buildFormData(request, attachmentName) {
      /**Builds form data used in DISCORD upload request*/

      let formData = new FormData()
      let attachmentJson = []

      for (let i = 0; i < request.attachments.length; i++) {
         const attachment = request.attachments[i]
         const encryptedBlob = await encryptAttachment(attachment)
         formData.append(`files[${i}]`, encryptedBlob, attachmentName)
         attachmentJson.push({ id: i, filename: attachmentName })
      }

      formData.append("json_payload", JSON.stringify({ attachments: attachmentJson }))
      return formData
   }

   buildDiscordAxiosConfig(request, abortSignal) {
      const uploadStore = this.uploadStore
      let totalBytesUploaded = 0

      return {
         onUploadProgress: (progressEvent) => {
            totalBytesUploaded = progressEvent.loaded
            if (!progressEvent.rate) progressEvent.rate = 0
            uploadStore.onUploadProgress(request, progressEvent)
         },

         onErrorCallback: (error) => {
            uploadStore.fixUploadTracking(request, totalBytesUploaded, error)
         },

         onRequestFinish: () => {
            let missing = request.totalSize - totalBytesUploaded
            if (missing < 0) missing = 0
            console.log("Missing bytes:", missing)
            uploadStore.fixMissingBytesFromRequest(request, missing)
         },

         signal: abortSignal
      }
   }

   createAbortController(request) {
      let controller = new AbortController()
      this.abortRequestMap.set(request.id, controller)
      return controller
   }

   handleFatalUploadError(err, request) {
      /**Handles axios error in DISCORD upload request*/
      console.log("handleFatalUploadError")
      this.failedRequests.push(request)

      if (!axios.isCancel(err)) {
         if (noWifi(err)) {
            this.uploadStore.setState(uploadState.noInternet)
         }

         if (err.response?.data?.code === 10015) {
            toast.error(`${i18n.global.t("toasts.unknownWebhook", { "webhook": err.config.__webhook.name })}`, { timeout: null })
            this.uploadStore.pauseAll()
         }

         request.attachments.forEach(att => {
            if (noWifi(err)) {
               this.uploadStore.setStatus(att.fileObj.frontendId, fileUploadStatus.waitingForInternet)

            } else {
               this.uploadStore.setStatus(att.fileObj.frontendId, fileUploadStatus.uploadFailed)
               this.uploadStore.setError(att.fileObj.frontendId, err.message)
            }
         })
      }
   }

   async uploadRequest(request) {
      let attachmentName = this.uploadStore.attachmentName

      if (this.uploadStore.state === uploadState.paused) {
         this.uploadStore.addPausedRequest(request)
         let err = Error("Upload is paused!")
         err.handled = true
         throw err
      }

      let formData = await this.buildFormData(request, attachmentName)
      let controller = this.createAbortController(request)
      let config = this.buildDiscordAxiosConfig(request, controller.signal)

      try {
         await this.setStatusForRequest(request, fileUploadStatus.uploading)
         let discordResponse = await upload(formData, config)
         this.abortRequestMap.delete(request.id)
         return { request, discordResponse }
      } catch (err) {
         this.handleFatalUploadError(err, request)
         err.handled = true
         throw err
      }
   }

   async setStatusForRequest(request, status) {
      for (let i = 0; i < request.attachments.length; i++) {
         let frontendId = request.attachments[i].fileObj.frontendId
         this.uploadStore.setStatus(frontendId, status)
      }
   }

   pauseAllRequests() {
      for (const controller of this.abortRequestMap.values()) {
         controller.abort()
      }

      this.abortRequestMap.clear()
   }

   async reUploadRequest(frontendId) {
      for (let i = 0; i < this.failedRequests.length; i++) {
         const request = this.failedRequests[i]

         for (const attachment of request.attachments) {
            if (attachment.fileObj.frontendId === frontendId) {
               await this.setStatusForRequest(request, fileUploadStatus.retrying)
               await this.uploadStore.addPausedRequest(request)
               this.failedRequests.splice(i, 1) // Remove the request from failedRequests
               break
            }
         }
      }
   }
}
