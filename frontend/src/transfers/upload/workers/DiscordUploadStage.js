import axios from "axios"
import { upload } from "@/transfers/upload/utils/uploadHelper.js"
import { noWifi } from "@/axios/helper.js"
import { encryptAttachment } from "@/utils/crypto/encryption.js"
import { PipelineWorker } from "@/transfers/shared/base/PipelineWorker.js"
import { workerExitReason } from "@/transfers/shared/constants.js"
import { uploadFileStatus, uploadState } from "@/transfers/upload/constants.js"
import { useTransferStore } from "@/stores/transferStore.js"

export class DiscordUploadStage extends PipelineWorker {
   constructor({ requestQueue, discordResponseQueue, uploadRuntime, onFailedRequest }) {
      super()

      this.transferStore = useTransferStore()
      this.requestQueue = requestQueue
      this.discordResponseQueue = discordResponseQueue
      this.uploadRuntime = uploadRuntime
      this.onFailedRequest = onFailedRequest

      this.abortRequestMap = new Map()
   }

   kill() {
      this.abortAllUploadRequests()
      return super.kill()
   }

   async run() {
      if (this._running) {
         console.warn("DiscordUploadConsumer is already running!")
         return workerExitReason.stopped
      }

      const signal = this._markStarted()
      let exitReason = workerExitReason.stopped

      try {
         while (!signal.aborted) {
            if (this._stopRequested) {
               exitReason = workerExitReason.stopped
               break
            }

            if (this.uploadRuntime.uploadState !== uploadState.uploading) {
               await this.uploadRuntime.waitUntilResumed(signal)
               continue
            }

            const request = await this.takeWithAbort(this.requestQueue, signal)
            if (!request) {
               exitReason = workerExitReason.inputEnded
               break
            }

            try {
               const discordResponse = await this.uploadSingleRequest(request, signal)
               await this.putWithAbort(this.discordResponseQueue, { request, discordResponse }, signal)
            } catch (error) {
               if (error.handled) continue
               this.onRequestUnhandledError(request, error)
            }
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

   async uploadSingleRequest(request, signal) {
      const attachmentName = this.transferStore.upload.attachmentName

      try {
         const formData = await this.buildFormData(request, attachmentName)
         const controller = this.createAbortController(request)
         const config = this.buildDiscordAxiosConfig(request, controller.signal)

         await this.setStatusForRequest(request, uploadFileStatus.uploading)
         return await upload(formData, config)
      } catch (err) {
         await this.handleUploadError(err, request, signal)
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
         } catch (err) {
            if (err.name === "NotFoundError") {
               const fileGoneError = new Error()
               fileGoneError.name = "FileGone"
               fileGoneError.frontendId = attachment.fileObj.frontendId
               throw fileGoneError
            }

            throw err
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
         onUploadProgress: (progressEvent) => {
            totalBytesUploaded = progressEvent.loaded
            if (!progressEvent.rate) progressEvent.rate = 0
            this.uploadRuntime.onUploadProgress(request, progressEvent)
         },
         onErrorCallback: (error) => {
            this.uploadRuntime.fixUploadTracking(request, totalBytesUploaded, error)
         },
         signal: abortSignal
      }
   }

   createAbortController(request) {
      const controller = new AbortController()
      this.abortRequestMap.set(request.id, controller)
      return controller
   }

   async handleUploadError(err, request, signal) {
      if (axios.isCancel(err)) {
         if (!this._killed && this.isRunning()) {
            await this.putWithAbort(this.requestQueue, request, signal, {force: true})
         }

         err.handled = true
      }

      else if (noWifi(err)) {
         await this.putWithAbort(this.requestQueue, request, signal, { force: true })
         this.uploadRuntime.setUploadingState(uploadState.noInternet)
         err.handled = true
      }

      else if (err.name === "FileGone") {
         const fileState = this.uploadRuntime.getFileState(err.frontendId)
         fileState.setStatus(uploadFileStatus.fileGoneInUpload)
         this.onFailedRequest(request)
         err.handled = true
      }

      else if (axios.isAxiosError(err)) {
         request.attachments.forEach(att => {
            const fileState = this.uploadRuntime.getFileState(att.fileObj.frontendId)
            fileState.setStatus(uploadFileStatus.uploadFailed)
            fileState.setError(err.message)
         })

         this.onFailedRequest(request)
         err.handled = true
      }

      throw err
   }

   async setStatusForRequest(request, status) {
      for (let i = 0; i < request.attachments.length; i++) {
         const frontendId = request.attachments[i].fileObj.frontendId
         this.uploadRuntime.getFileState(frontendId).setStatus(status)
      }
   }

   abortAllUploadRequests() {
      for (const controller of this.abortRequestMap.values()) {
         controller.abort()
      }

      this.abortRequestMap.clear()
   }

   onRequestUnhandledError(request, error) {
      for (const attachment of request.attachments) {
         const frontendId = attachment.fileObj.frontendId
         const fileState = this.uploadRuntime.getFileState(frontendId)
         fileState.setStatus(uploadFileStatus.errorOccurred)
         fileState.setError(error)
      }
   }
}