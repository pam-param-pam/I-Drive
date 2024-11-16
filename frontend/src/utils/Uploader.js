import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { useUploadStore } from "@/stores/uploadStore.js"
import { UploadEstimator } from "@/utils/UploadEstimator.js"
import { attachmentType } from "@/utils/constants.js"
import { prepareRequests, preUploadRequest, uploadRequest } from "@/utils/upload.js"

export class Uploader {
   constructor() {
      this.fileProcessorWorker = new Worker(new URL('../workers/fileProcessorWorker.js', import.meta.url), { type: 'module' });
      // this.requestGeneratorWorker = new Worker(new URL('../workers/requestGeneratorWorker.js.js', import.meta.url), { type: 'module' });

      this.estimator = new UploadEstimator()

      this.requestBuffer = []
      this.requestGenerator = prepareRequests()


      this.mainStore = useMainStore()
      this.uploadStore = useUploadStore()

      this.fileProcessorWorker.onmessage = (event) => {
         this.uploadStore.queue.push(...event.data)
         this.uploadStore.queue.sort()
         this.uploadStore.processUploads()
      };

      // this.requestGeneratorWorker.onmessage = (event) => {
      //
      //    console.log(event)
      // };
   }

   processNewFiles(typeOfUpload, folderContext, filesList) {
      /**
       This method converts different uploadInputs into 1, standard one
       */

      let uploadId = uuidv4()
      let encryptionMethod = this.mainStore.settings.encryptionMethod

      this.fileProcessorWorker.postMessage({typeOfUpload, folderContext, filesList, uploadId, encryptionMethod});


   }
   async startUploading() {

      if (this.requestBuffer.length < 2) {
         this.requestGeneratorWorker.postMessage(this.requestGenerator);
      }

   }

}
