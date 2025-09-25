import axios from "axios"
import { encryptAttachment } from "@/utils/encryption.js"
import { fileUploadStatus, uploadState } from "@/utils/constants.js"
import { upload } from "@/upload/uploadHelper.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { noWifi } from "@/axios/helper.js"

export class DiscordUploader {
   constructor() {
      this.uploadStore = useUploadStore()
      this.abortRequestMap = new Map()
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
      /**Builds axios config used in DISCORD upload request*/

      let totalBytesUploaded = 0
      const uploadStore = this.uploadStore

      return {
         onUploadProgress: (progressEvent) => {
            totalBytesUploaded = progressEvent.loaded
            if (progressEvent.rate) {
               uploadStore.onUploadProgress(request, progressEvent)
            }
         },
         /**This is called internally by networker*/
         onErrorCallback: (error) => {
            //todo display info like error retring...
            uploadStore.fixUploadTracking(request, totalBytesUploaded, error)
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
      this.uploadStore.addFailedRequest(request)

      if (!axios.isCancel(err)) {
         if (noWifi(err)) {
            this.uploadStore.setState(uploadState.noInternet)
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
      throw err
   }

   async uploadRequest(request) {
      let attachmentName = this.uploadStore.attachmentName

      if (this.uploadStore.state === uploadState.paused) {
         this.uploadStore.addPausedRequest(request)
         throw Error("Upload is paused!")
      }

      let formData = await this.buildFormData(request, attachmentName)
      let controller = this.createAbortController(request)
      let config = this.buildDiscordAxiosConfig(request, controller.signal)

      try {
         await this.setUploadingStatus(request)
         let discordResponse = await upload(formData, config)
         this.abortRequestMap.delete(request.id)
         return { request, discordResponse }
      } catch (err) {
         this.handleFatalUploadError(err, request)
         throw err
      }
   }

   async setUploadingStatus(request) {
      for (let i = 0; i < request.attachments.length; i++) {
         let frontendId = request.attachments[i].fileObj.frontendId
         this.uploadStore.setStatus(frontendId, fileUploadStatus.uploading)
      }
   }

   pauseAllRequests() {
      for (const controller of this.abortRequestMap.values()) {
         controller.abort()
      }

      this.abortRequestMap.clear()
   }
}
