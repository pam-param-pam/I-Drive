import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { useUploadStore } from "@/stores/uploadStore.js"
import { uploadState } from "@/utils/constants.js"
import { canUpload } from "@/api/user.js"

import { DiscordUploader } from "@/upload/DiscordUploader.js"
import { RequestGenerator } from "@/upload/RequestGenerator.js"
import { BackendManager } from "@/upload/BackendManager.js"
import { UploadEstimator } from "@/upload/UploadEstimator.js"
import { MyMutex } from "@/utils/MyMutex.js"


export class Uploader {
   constructor() {
      this.fileProcessorWorker = null
      this.estimator = new UploadEstimator()

      this.discordUploader = new DiscordUploader()
      this.backendManager = new BackendManager()
      this.requestGenerator = new RequestGenerator(this.backendManager)

      this.mainStore = useMainStore()
      this.uploadStore = useUploadStore()
      this.mutex = new MyMutex()

   }

   async startUpload(type, folderContext, filesList) {
      /**Entry for upload process*/
      // window.addEventListener("beforeunload", beforeUnload)
      this.uploadStore.state = uploadState.uploading

      let res = await canUpload(folderContext)
      if (!res.can_upload) return

      this.processNewFiles(type, folderContext, filesList, res.lockFrom)
      //todo NotOptimizedForSmallFiles
   }

   processNewFiles(typeOfUpload, folderContext, filesList, lockFrom) {
      /**This method converts different uploadInputs into 1, standard one*/
      let uploadId = uuidv4()
      let encryptionMethod = this.mainStore.settings.encryptionMethod
      let parentPassword = this.mainStore.getFolderPassword(lockFrom)

      this.fileProcessorWorker = new Worker(new URL("../workers/fileProcessorWorker.js", import.meta.url), { type: "module" })
      this.fileProcessorWorker.onmessage = (event) => {
         let { files, totalBytes } = event.data
         this.uploadStore.queue.push(...files)
         this.uploadStore.queue.sort()
         this.uploadStore.allBytesToUpload += totalBytes
         this.processUploads()
         this.fileProcessorWorker.terminate()
      }

      this.fileProcessorWorker.postMessage({ typeOfUpload, folderContext, filesList, uploadId, encryptionMethod, parentPassword, lockFrom })

   }

   async processUploads() {
      if (!(this.uploadStore.state === uploadState.uploading || this.uploadStore.state === uploadState.idle)) return

      // Acquire the mutex before checking/modifying currentRequests
      const unlock = await this.mutex.lock()
      let req = null
      try {
         const maxConcurrency = this.mainStore.settings.concurrentUploadRequests
         if (this.uploadStore.currentRequests >= maxConcurrency) return

         req = await this.requestGenerator.getRequest()
         if (!req) return

         this.uploadStore.currentRequests++

         // Start the upload without blocking the mutex
         this.discordUploader.uploadRequest(req)
            .then(({ request, discordResponse }) => this.backendManager.afterUploadRequest(request, discordResponse))
            .catch(err => {
               this.uploadStore.onGeneralError(err, req)
            })
            .finally(() => {
               // Critical section for decrementing
               this.mutex.lock().then(unlockInner => {
                  this.uploadStore.currentRequests--
                  unlockInner()
                  this.processUploads()
               })
            })
      } finally {
         unlock() // release mutex
      }
      this.processUploads()
   }

   cleanup() {
      window.removeEventListener("beforeunload", beforeUnload)
      this.estimator = new UploadEstimator()
      this.discordUploader = new DiscordUploader()
      this.backendManager = new BackendManager()
      this.requestGenerator = new RequestGenerator(this.backendManager)
   }
}

let _uploaderInstance = null


export function getUploader() {
   if (!_uploaderInstance) {
      _uploaderInstance = new Uploader()
   }
   return _uploaderInstance
}


const beforeUnload = (event) => {
   event.preventDefault()
   event.returnValue = ""
}