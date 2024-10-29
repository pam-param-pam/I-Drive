import {defineStore} from "pinia"
import buttons from "@/utils/buttons.js"
import {
   convertUploadInput,
   prepareRequests,
   uploadRequest
} from "@/utils/upload2.js"
import {useMainStore} from "@/stores/mainStore.js";
import { v4 as uuidv4 } from 'uuid';

export const useUploadStore = defineStore('upload2', {
   state: () => ({
      queue: [],
      requestsUploading: [],

      currentRequests: 0,

      //UI
      uploadSpeedMap: new Map(),
      progressMap: new Map(),
      etaMap: new Map(),

      //experimental
      axiosRequests: [],
      pausedFiles: [],
      filesUploading: [],


      //simply dumb
      requestGenerator: null
   }),

   getters: {
      uploadSpeed() {

      },
      eta() {

      },
      filesInUploadCount() {
         // let queue = this.queue.length
         // let requestQueue = this.requestQueue.reduce((acc, obj) => acc + obj.numberOfFiles, 0);
         // let requestsUploading = this.requestsUploading.reduce((acc, obj) => acc + obj.numberOfFiles, 0);
         //
         // return queue + requestQueue + requestsUploading
         return 0

      },
      filesInUpload() {
         // return this.requestsUploading

         // return files.sort((a, b) => a.progress - b.progress).slice(0, 10)
         // return files.sort((a, b) => a.progress - b.progress)
         return []
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

         let canProcess = this.currentRequests < mainStore.settings.concurrentUploadRequests
         if (!canProcess) return

         if (!this.requestGenerator) {
            this.requestGenerator = prepareRequests()
         }
         let generated = this.requestGenerator.next()


         if (generated.done) {
            console.info("The request generator is finished.")
            this.requestGenerator = null
            return
         }
         let request = generated.value

         this.currentRequests++

         console.log("request")
         console.log(request)

         request.id =  Math.random().toString(16).slice(2)
         uploadRequest(request)

         this.processUploads()

      },

      getFileFromQueue() {
         console.info("GETING FILE FROM QUEUE: ")

         if (this.queue.length === 0) {
            console.warn("getFileFromQueue is empty, yet it was called idk why")
            return
         }

         let file = this.queue[0];

         file.frontendId = uuidv4();
         this.filesUploading.push(file)

         this.queue.shift(); // Remove the file from the queue
         return file
         }

      },
      finishFileUpload(file_id) {

      },
      setStatus(file_id, status) {

      },
      setProgress(file_id, loadedBytes) {

      },
      setMultiAttachmentProgress(file_ids, progress) {

      },
      removeFileFromUpload(file_id) {

      },
      setUploadSpeedBytes(requestId, value) {

      },
      setETA(requestId, value) {

      },
      resetUpload() {

      },
      abortAll() {

      },

})
const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}