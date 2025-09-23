import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { useUploadStore } from "@/stores/uploadStore.js"
import { uploadState } from "@/utils/constants.js"
import { canUpload } from "@/api/user.js"

import { DiscordUploader } from "@/upload/DiscordUploader.js"
import { RequestGenerator } from "@/upload/RequestGenerator.js"
import { BackendManager } from "@/upload/BackendManager.js"
import { UploadEstimator } from "@/upload/UploadEstimator.js"


export class Uploader {
   constructor() {
      this.fileProcessorWorker = new Worker(new URL("../workers/fileProcessorWorker.js", import.meta.url), { type: "module" })

      this.estimator = new UploadEstimator()

      this.requestGenerator = null

      this.discordUploader = new DiscordUploader()
      this.backendManager = new BackendManager()
      this.requestGenerator = new RequestGenerator(this.backendManager)
      this.currentConcurrency = 0

      this.mainStore = useMainStore()
      this.uploadStore = useUploadStore()

      this.fileProcessorWorker.onmessage = (event) => {
         this.uploadStore.queue.push(...event.data)
         this.uploadStore.queue.sort()
         this.processUploads()
      }
   }

   async startUpload(type, folderContext, filesList) {
      /**Entry for upload process*/
      // window.addEventListener("beforeunload", beforeUnload)
      this.state = uploadState.uploading

      let res = await canUpload(folderContext)
      if (!res.can_upload) {
         return
      }
      this.processNewFiles(type, folderContext, filesList, res.lockFrom)
      //todo NotOptimizedForSmallFiles
   }

   processNewFiles(typeOfUpload, folderContext, filesList, lockFrom) {
      /**This method converts different uploadInputs into 1, standard one*/
      let uploadId = uuidv4()
      let encryptionMethod = this.mainStore.settings.encryptionMethod
      let parentPassword = this.mainStore.getFolderPassword(lockFrom)
      this.fileProcessorWorker.postMessage({ typeOfUpload, folderContext, filesList, uploadId, encryptionMethod, parentPassword })

   }


   async processUploads() {
      /** This function is the main loop of the upload process*/
      if (!(this.uploadStore.state === uploadState.uploading || this.uploadStore.state === uploadState.idle)) {
         console.log("WRONG STATE IN processUploads, RETURNING")
         return
      }
      const maxConcurrency = this.mainStore.settings.concurrentUploadRequests
      if (this.currentConcurrency >= maxConcurrency) return

      let req = await this.requestGenerator.getRequest()
      if (!req) {
         console.log("No requests, returning")
         return
      }

      this.currentConcurrency++

      this.discordUploader.uploadRequest(req)
         .then(({ request, discordResponse }) => this.backendManager.afterUploadRequest(request, discordResponse))
         .finally(() => {
            this.currentConcurrency--
            this.processUploads()
         })

      this.processUploads()
   }

   async pauseAllFiles() {
      this.discordUploader.pauseAllRequests()
   }


}

let _uploaderInstance = null


export function getUploader() {
   if (!_uploaderInstance) {
      _uploaderInstance = new Uploader()
   }
   return _uploaderInstance
}