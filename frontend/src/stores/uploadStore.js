import { defineStore } from "pinia"
import { prepareRequests, uploadRequest } from "@/utils/upload.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, fileUploadStatus, uploadState } from "@/utils/constants.js"
import buttons from "@/utils/buttons.js"
import { useToast } from "vue-toastification"
import { Uploader } from "@/utils/Uploader.js"
import { canUpload } from "@/api/user.js"
import { createFile } from "@/api/files.js"
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

      state: uploadState.idle,
      uploadSpeedList: [],
      fileExtensions: null
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
         return this.filesUploading
            .sort((a, b) => b.progress - a.progress)
            .slice(0, 10)
            .map(file => file.fileObj)

      },
      remainingBytes() {
         let totalQueueSize = this.queue.reduce((total, item) => total + item.fileObj.size, 0)

         let remainingUploadSize = this.filesUploading.reduce((total, item) => {

            let uploadedSize = item.fileObj.size * (item.fileObj.progress / 100)
            let remainingSize = item.fileObj.size - uploadedSize
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
         return 0
      }

   },

   actions: {
      async startUpload(type, folderContext, filesList) {
         // window.addEventListener("beforeunload", beforeUnload)

         this.state = uploadState.uploading

         let res = await canUpload(folderContext)
         if (!res.can_upload) {
            return
         }

         this.uploader.processNewFiles(type, folderContext, filesList, res.lockFrom)
         //todo NotOptimizedForSmallFiles

      },

      async processUploads() {
         const mainStore = useMainStore()
         let canProcess = this.concurrentRequests < mainStore.settings.concurrentUploadRequests && (this.state === uploadState.uploading || this.state === uploadState.idle)
         // console.log("this.concurrentRequests")
         // console.log(this.concurrentRequests)
         // console.log(canProcess)
         if (!canProcess) return
         this.concurrentRequests++

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
               this.concurrentRequests--
               return
            }
            request = generated.value
            request.id = uuidv4()
         }

         uploadRequest(request)

         this.processUploads()

      },
      getFileFromQueue() {

         if (this.queue.length === 0) {
            console.warn("getFileFromQueue is empty, yet it was called idk why")
            return
         }

         let file = this.queue[0]

         file.fileObj.status = fileUploadStatus.preparing
         file.fileObj.progress = 0

         this.filesUploading.push(file)

         this.queue.shift() // Remove the file from the queue
         return file
      },
      setStatus(frontendId, status) {
         let file = this.filesUploading.find(item => item.fileObj.frontendId === frontendId)
         if (file) {
            if (status === fileUploadStatus.uploaded && this.state === uploadState.paused) return
            file.fileObj.status = status
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the queue.`)
         }
      },
      finishFileUpload(frontendId) {
         this.setStatus(frontendId, fileUploadStatus.uploaded)
         setTimeout(() => {
            //remove file from filesUploading
            this.filesUploading = this.filesUploading.filter(item => item.fileObj.frontendId !== frontendId)

         }, 2000)

      },
      setProgress(frontendId, percentage) {
         let file = this.filesUploading.find(item => item.fileObj.frontendId === frontendId)
         if (file) {
            file.fileObj.progress = percentage
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
         if (this.concurrentRequests > 0) {
            this.concurrentRequests--
         }
         else {
            console.warn("this.concurrentRequests is <= 0")
            console.warn(this.concurrentRequests)
         }
      },
      abortAll() {

      },
      abortFile(frontendId) {

      },
      tryAgain(frontendId) {
         let index = this.filesUploading.findIndex(file => file.fileObj.frontendId === frontendId)

         if (index !== -1) {
            let file = this.filesUploading[index]
            console.log(file)
            this.filesUploading.splice(index, 1)

            this.queue.unshift(file)
            this.processUploads()
         }
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
         this.filesUploading.forEach(file => file.fileObj.status = fileUploadStatus.paused)
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
      setFileExtensions(value) {
         this.fileExtensions = value
      },

      //experimental
      fillAttachmentInfo(attachment, discordResponse, discordAttachment) {
         let fileObj = attachment.fileObj
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
            state.crc = fileObj.crc >>> 0
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
               "message_author_id": discordResponse.data.author.id
            }
         } else if (attachment.type === attachmentType.videoMetadata) {
            state.videoMetadata = {
               "mime": attachment.mime,
               "is_progressive": attachment.is_progressive,
               "is_fragmented": attachment.is_fragmented,
               "has_moov": attachment.has_moov,
               "has_IOD": attachment.has_IOD,
               "brands": attachment.brands,
               "video_tracks": attachment.video_tracks,
               "audio_tracks": attachment.audio_tracks,
               "subtitle_tracks": attachment.subtitle_tracks
            }
         }
         this.backendState.set(fileObj.frontendId, state)
         if (state.attachments.length === fileObj.totalChunks && (!fileObj.thumbnail || state.thumbnail) && (!fileObj.type.includes("video") || state.videoMetadata || fileObj.mp4boxFinished)) {
            this.finishedFiles.push(state)
            if (!state.videoMetadata) console.warn("videoMetadata is missing")
            this.finishFileUpload(fileObj.frontendId)
         }
         let totalSize = 0
         for (let finishedFile of this.finishedFiles) {
            totalSize += finishedFile.size
         }
         if (this.finishedFiles.length > 20 || totalSize > 100 * 1024 * 1024 || (this.isUploadFinished && this.finishedFiles.length > 0)) {
            let finishedFiles = this.finishedFiles
            this.finishedFiles = []
            createFile({ "files": finishedFiles }, fileObj.parentPassword).catch((error) => {
               // for (let file of finishedFiles) {
               //    this.filesUploading.push(file.fileObj)
               //    this.setStatus(file.frontendId, fileUploadStatus.failed)
               // }
               //todo HANDLE THIS OMFG
            })

         }
      }
   }
})

const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}