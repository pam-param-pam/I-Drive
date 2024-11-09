import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { uploadType } from "@/utils/constants.js"

export class Uploader {
   constructor() {
      this.fileProcessorWorker = new Worker(new URL('../workers/fileProcessorWorker.js', import.meta.url), { type: 'module' });


      console.log(this.fileProcessorWorker)
   }

   processNewFiles(typeOfUpload, folderContext, filesList) {
      /**
       This method converts different uploadInputs into 1, standard one
       */

      let mainStore = useMainStore()

      let uploadId = uuidv4()
      let encryptionMethod = mainStore.settings.encryptionMethod

      this.fileProcessorWorker.postMessage({typeOfUpload, folderContext, filesList, uploadId, encryptionMethod});
      // worker.onmessage = (event) => {
            //    // //todo handle files.size == 0
            //    // this.queue.push(...event.data)
            //    // this.queue.sort()
            //    //
            //    // this.processUploads()
            // };

   }

}
