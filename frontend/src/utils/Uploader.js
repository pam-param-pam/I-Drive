import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { useUploadStore } from "@/stores/uploadStore.js"
import { UploadEstimator } from "@/utils/UploadEstimator.js"

export class Uploader {
   constructor() {
      this.fileProcessorWorker = new Worker(new URL("../workers/fileProcessorWorker.js", import.meta.url), { type: "module" })

      this.estimator = new UploadEstimator()

      this.mainStore = useMainStore()
      this.uploadStore = useUploadStore()

      this.fileProcessorWorker.onmessage = (event) => {
         this.uploadStore.queue.push(...event.data)
         this.uploadStore.queue.sort()
         this.uploadStore.processUploads()
      }
   }

   processNewFiles(typeOfUpload, folderContext, filesList, lockFrom) {
      /**
       This method converts different uploadInputs into 1, standard one
       */

      let uploadId = uuidv4()
      let encryptionMethod = this.mainStore.settings.encryptionMethod
      let parentPassword = this.mainStore.getFolderPassword(lockFrom)
      this.fileProcessorWorker.postMessage({ typeOfUpload, folderContext, filesList, uploadId, encryptionMethod, parentPassword })


   }
}
