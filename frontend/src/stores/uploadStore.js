import { defineStore } from "pinia"
import { prepareRequests, preUploadRequest, uploadRequest } from "@/utils/upload.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, uploadStatus } from "@/utils/constants.js"
import buttons from "@/utils/buttons.js"
import { useToast } from "vue-toastification"
import { Uploader } from "@/utils/Uploader.js"

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
      requestGenerator: null,
      uploader: new Uploader(),

      eta: Infinity,

      bufferedRequests: [],
   }),

   getters: {
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

         this.uploader.processNewFiles(type, folderContext, filesList)
         //todo NotOptimizedForSmallFiles

      },
      // async bufferRequests() {
      //    if (!this.requestGenerator) {
      //       this.requestGenerator = prepareRequests()
      //    }
      //
      //    if (this.bufferedRequests.length < 1) {
      //       this.requestGenerator.next().then((generated) => {
      //          if (generated.done) {
      //             console.info("The request generator is finished.")
      //             this.requestGenerator = null
      //             return
      //          }
      //          this.bufferedRequests.push(generated.value);
      //       });
      //
      //    }
      //
      //
      // },
      async processUploads() {
         const mainStore = useMainStore()
         console.log("this.concurrentRequests")
         console.log(this.concurrentRequests)
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
         console.log(request.totalSize)

         request = await preUploadRequest(request)

         uploadRequest(request)

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
         console.log("finishRequest")
         console.log(requestId)
         buttons.success("upload")

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
         let abortController = this.axiosRequests.get("blabla")
         if (abortController) {
            abortController.abort() // Cancel the request
            console.log("Upload request canceled by user.")
         }
      }
   }
})
const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}