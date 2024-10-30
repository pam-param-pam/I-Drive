import {defineStore} from "pinia"
import {
   convertUploadInput,
   prepareRequests, preUploadRequest,
   uploadRequest
} from "@/utils/upload2.js"
import {useMainStore} from "@/stores/mainStore.js";
import { v4 as uuidv4 } from 'uuid';
import { uploadStatus } from "@/utils/constants.js"

export const useUploadStore = defineStore('upload2', {
   state: () => ({
      queue: [],
      requestsUploading: [],

      concurrentRequests: 0,

      //UI
      uploadSpeedMap: new Map(),
      progressMap: new Map(),
      etaMap: new Map(),

      //experimental
      axiosRequests: [],
      pausedFiles: [],
      filesUploading: [],
      createdFolders: new Map(),
      createdFiles: new Map(),

      //simply dumb
      requestGenerator: null
   }),

   getters: {
      uploadSpeed() {
         return 0
      },
      eta() {
         return 0

      },
      filesInUploadCount() {
         let queue = this.queue.length
         let filesUploading = this.filesUploading.length

         return queue + filesUploading

      },
      progress() {

      },

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

         this.queue.shift(); // Remove the file from the queue
         return file
      },
      setStatus(frontendId, status) {
         let file = this.filesUploading.find(item => item.frontendId === frontendId);
         if (file) {
            file.status = status;
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the queue.`);
         }
      },
      finishFileUpload(frontendId) {
         this.setStatus(frontendId, uploadStatus.uploaded)
         setTimeout(() => {
            //remove file from filesUploading
            this.filesUploading = this.filesUploading.filter(item => item.file_id !== frontendId)

         }, 3500)

      },
      setProgress(frontendId, percentage) {
         let file = this.filesUploading.find(item => item.frontendId === frontendId);
         if (file) {
            file.progress = percentage;
         } else {
            console.warn(`File with frontedId ${frontendId} not found in the queue.`);
         }
      },
      setMultiAttachmentProgress(file_ids, progress) {

      },
      removeFileFromUpload(file_id) {

      },
      finishRequest(requestId) {
         console.log("finishRequest")
         console.log(requestId)
         this.concurrentRequests--
         //this.uploadSpeedMap.delete(requestId)
         //this.etaMap.delete(requestId)

         this.processUploads()
      },
      setUploadSpeedBytes(requestId, value) {

      },
      setETA(requestId, value) {

      },
      resetUpload() {

      },
      abortAll() {

      },

   }
})
const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}