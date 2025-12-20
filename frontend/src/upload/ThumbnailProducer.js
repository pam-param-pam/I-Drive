import { attachmentType } from "@/utils/constants.js"
import { v4 as uuidv4 } from "uuid"
import { fastVideoThumbnail } from "@/upload/utils/uploadHelper.js"

export class ThumbnailProducer {
   constructor({ uploadRuntime, requestQueue }) {
      this.uploadRuntime = uploadRuntime
      this.requestQueue = requestQueue
      this.running = false
   }

   async generate(queueFile) {
      if (this.running) return
      this.running = true

      try {
         const state = this.uploadRuntime.getFileState(queueFile.fileObj.frontendId)

         if (state.thumbnailExtracted) return

         console.log("THUMBNAIL start", queueFile.fileObj.name)

         const thumbnail = await fastVideoThumbnail(queueFile)

         if (!thumbnail) return

         console.log("THUMBNAIL done", queueFile.fileObj.name)

         state.markThumbnailExtracted(queueFile.fileObj.frontendId)

         // enqueue thumbnail as a separate request
         this.requestQueue.put({
            id: uuidv4(),
            totalSize: thumbnail.size,
            attachments: [{
               type: attachmentType.thumbnail,
               fileObj: queueFile.fileObj,
               rawBlob: thumbnail
            }]
         })
      } catch (err) {
         console.error("Thumbnail failed", err)
      } finally {
         this.running = false
      }
   }
}
