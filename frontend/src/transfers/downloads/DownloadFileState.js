import { downloadFileStatus } from "@/transfers/downloads/constants.js"
import { BaseTransferFileState } from "@/transfers/shared/base/BaseTransferFileState.js"
import { isErrorStatus } from "@/transfers/downloads/helper.js"

export class DownloadFileState extends BaseTransferFileState {
   constructor(file, fieldChangeCallback) {
      super(file.id, fieldChangeCallback, {
         initialStatus: downloadFileStatus.queued,
         size: file.size,
         retryStatus: downloadFileStatus.retrying,
         isErrorStatus
      })

      this.fileObj = file
   }

   onDownloadProgress(progressEvent) {
      const bytes = progressEvent.bytes
      const loaded = progressEvent.loaded
      const total = progressEvent.total

      if (total !== undefined) {
         this.setTransferredBytes(total)
      }

      if (loaded !== undefined) {
         this.setTransferredBytes(loaded)
      } else if (bytes > 0) {
         this.updateTransferredBytes(bytes)
      }
   }

   isFinished() {
      return this.status === downloadFileStatus.completed
   }
}