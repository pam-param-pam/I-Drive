import { defineStore } from "pinia"
import { convertUploadInput, prepareRequests, preUploadRequest, uploadRequest } from "@/utils/upload2.js"
import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { attachmentType, uploadStatus } from "@/utils/constants.js"
import buttons from "@/utils/buttons.js"
import { useToast } from "vue-toastification"

const toast = useToast()

export const useUploadStore = defineStore("upload2", {
   state: () => ({
      queue: [],
      concurrentRequests: 0,
      filesUploading: [],

      createdFolders: new Map(),
      createdFiles: new Map(),

      //UI
      uploadSpeedMap: new Map(),
      progressMap: new Map(),

      //experimental
      axiosRequests: new Map(),
      pausedFiles: [],

      //simply dumb
      requestGenerator: null
   }),

   getters: {
      uploadSpeed() {
         let uploadSpeed = Array.from(this.uploadSpeedMap.values()).reduce((sum, value) => sum + value, 0)
         if (isNaN(uploadSpeed)) {
            return 0
         }

         return uploadSpeed
      },
      eta() {
         //calc all
         // Sum up total size in 'queue'
         let totalQueueSize = this.queue.reduce((total, item) => total + item.fileObj.size, 0)

         // Calculate remaining bytes to be uploaded in 'filesUploading'
         let remainingUploadSize = this.filesUploading.reduce((total, item) => {

            // Adjust progress to a decimal by dividing by 100
            let uploadedSize = item.size * (item.progress / 100)
            let remainingSize = item.size - uploadedSize;
            return total + remainingSize;
         }, 0);

         // Total size left to upload
         let totalSizeRemaining = totalQueueSize + remainingUploadSize

         // Calculate ETA in seconds
         let etaInSeconds = this.uploadSpeed > 0 ? totalSizeRemaining / this.uploadSpeed : Infinity

         return etaInSeconds
      },
      filesInUploadCount() {
         let queue = this.queue.length
         let filesUploading = this.filesUploading.length

         return queue + filesUploading

      },
      progress() {

      }

   },

   actions: {
      async startUpload(type, folder_context, filesList) {
         // buttons.loading("upload")
         // window.addEventListener("beforeunload", beforeUnload)

         let files = await convertUploadInput(type, folder_context, filesList)
         //todo handle files.size == 0
         this.queue.push(...files)
         this.queue.sort()

         this.processUploads()

      },
      async processUploads() {
         const mainStore = useMainStore()

         let canProcess = this.concurrentRequests < mainStore.settings.concurrentUploadRequests
         if (!canProcess) return

         if (!this.requestGenerator) {
            this.requestGenerator = prepareRequests()
         }
         let generated = await this.requestGenerator.next()


         if (generated.done) {
            console.info("The request generator is finished.")
            this.requestGenerator = null
            return
         }
         let request = generated.value
         this.concurrentRequests++

         console.log("request")
         console.log(request)

         request.id = uuidv4()
         request = await preUploadRequest(request) //todo only if request has chunked attachments

         uploadRequest(request) //todo else do it in here

         this.processUploads()

      },
      getFileFromQueue() {
         console.info("GETING FILE FROM QUEUE: ")

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

         }, 2500)

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
         this.uploadSpeedMap.set(request.id, progressEvent.rate)

         for (let attachment of request.attachments) {
            let frontendId = attachment.fileObj.frontendId

            if (attachment.type === attachmentType.entireFile) {
               let progress = progressEvent.progress
               let percentage = Math.round(progress * 100)
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
               let percentage = Math.round(totalLoadedBytes / attachment.fileObj.size * 100)
               this.setProgress(attachment.fileObj.frontendId, percentage)
            }
         }
      },
      finishRequest(requestId) {
         console.log("finishRequest")
         console.log(requestId)
         buttons.success("upload")

         this.concurrentRequests--
         this.uploadSpeedMap.delete(requestId)
         //this.etaMap.delete(requestId)

         this.processUploads()
      },

      abortAll() {

      },
      finishUpload() {
         this.requestGenerator = null
         this.queue = []
         this.filesUploading = []
         this.pausedFiles = []
         this.axiosRequests = new Map()
         this.createdFiles = new Map()
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
         let abortController = this.axiosRequests.get("blabla");
         if (abortController) {
            abortController.abort(); // Cancel the request
            console.log("Upload request canceled by user.");
         }
      },
   }
})
const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}