import {defineStore} from "pinia"
import buttons from "@/utils/buttons.js"
import { createNeededFolders, encryptWithAesCtr, encryptWithChaCha20, handleCreatingFiles, prepareRequests, uploadOneRequest } from "@/utils/upload.js"
import {useMainStore} from "@/stores/mainStore.js";


export const useUploadStore = defineStore('upload2', {
   state: () => ({
      queue: [],
      requestQueue: [],
      requestsUploading: [],

      //UI
      uploadSpeedMap: new Map(),
      progressMap: new Map(),
      etaMap: new Map(),

      //experimental
      axiosRequests: [],
      pausedFiles: [],
   }),

   getters: {
      uploadSpeed() {

      },
      eta() {

      },
      filesInUploadCount() {
         let queue = this.queue.length
         let requestQueue = this.requestQueue.reduce((acc, obj) => acc + obj.numberOfFiles, 0);
         let requestsUploading = this.requestsUploading.reduce((acc, obj) => acc + obj.numberOfFiles, 0);

         return queue + requestQueue + requestsUploading

      },
      filesInUpload() {
         // return this.requestsUploading

         // return files.sort((a, b) => a.progress - b.progress).slice(0, 10)
         // return files.sort((a, b) => a.progress - b.progress)
      },
      progress() {

      },

   },

   actions: {
      async startUpload(filesList, parent_folder) {
         buttons.loading("upload")
         window.addEventListener("beforeunload", beforeUnload)




      },
      async processUploads() {




      },

      async getFileFromQueue() {
         console.warn("GETING FILE FROM QUEUE: ")

         if (this.queue.length === 0) {
            console.warn("getFileFromQueue is empty, yet it was called idk why")
            return
         }
         while (this.queue.length > 0) {
            let file = this.queue[0];
            console.log(file.name)
            // Check if the file size is greater than 0
            if (file.size > 0) {
               this.queue.shift(); // Remove the file from the queue
               this.filesUploading.push(file); // Add the file to the filesUploading array


               // Process the file as needed
               return file;
            } else {
               // If the file size is 0, remove it from the queue and continue the loop
               this.queue.shift()
            }
         }

      },
      getRequestFromRequestQueue() {
         if (this.requestQueue.length === 0) {
            console.warn("getRequestFromRequestQueue is empty, yet it was called idk why")
            return
         }

         let request = this.requestQueue[0]
         request.requestId = Math.random().toString(16).slice(2)
         this.requestQueue.shift()
         if (request.type === "chunked") {
            //set source id policy to abort requests
         }
         if (request.type === "multiAttachment") {
            //set source id policy to abort requests
         }

         return request
      },
      addToQueue(item) {
         console.log(item)
         let file = {
            name: item.name,
            file_id: item.file_id,
            systemFile: item.file,
            size: item.file.size,
            parent_id: item.parent_id,
            type: item.type,
            encryption_key: item.encryption_key,
            encryption_iv: item.encryption_iv,
            is_encrypted: item.is_encrypted,
            status: "waiting",
            progress: 0
         }

         this.queue.push(file)

      },


      finishUpload(file_id) {
         let file_obj = this.getFileFromFilesUploading(file_id)
         if (!file_obj) return

         file_obj.status = "success"
         setTimeout(() => {
            this.removeFileFromUpload(file_id)

         }, 2500)

      },
      setStatus(file_id, status) {
         let file_obj = this.getFileFromFilesUploading(file_id)
         if (!file_obj) return

         file_obj.status = status

      },
      setProgress(file_id, loadedBytes) {
         let file_obj = this.getFileFromFilesUploading(file_id)
         if (!file_obj) return

         // Check if the key "file_id" exists
         if (this.progressMap.has(file_id)) {
            // Key exists, update the value
            let currentValue = this.progressMap.get(file_id)
            this.progressMap.set(file_id, currentValue + loadedBytes)
         } else {
            // Key does not exist, create it and set to 0
            this.progressMap.set(file_id, 0)
            file_obj.status = "uploading"

         }


         let totalLoadedBytes = this.progressMap.get(file_id)


         let percentage = Math.round( (totalLoadedBytes / file_obj.size) * 100)

         file_obj.progress = percentage

      },

      setMultiAttachmentProgress(file_ids, progress) {
         let percentage = Math.round(progress * 100)

         for (let file_id of file_ids) {
            let file_obj = this.getFileFromFilesUploading(file_id)
            if (!file_obj) continue

            file_obj.status = "uploading"
            file_obj.progress = percentage

         }
      },
      removeFileFromUpload(file_id) {
         this.filesUploading = this.filesUploading.filter(item => item.file_id !== file_id)

         let isFinished = this.queue.length === 0 && this.requestQueue.length === 0 && this.filesUploading.length === 0
         console.log("isFinished")
         console.log(isFinished)

         if (isFinished) {
            window.removeEventListener("beforeunload", beforeUnload)
            buttons.success("upload")
         }

      },
      setUploadSpeedBytes(requestId, value) {
         if (value === undefined) return
         this.uploadSpeedMap.set(requestId, value)

      },
      setETA(requestId, value) {
         console.log("set eta ")
         if (value === undefined) return
         this.etaMap.set(requestId, value)

      },
      resetUpload() {

      },
      abortAll() {
         //todo
         this.currentRequests = []
         this.queue = []

      },

   }
})
const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}