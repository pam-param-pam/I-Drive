import { BaseTransferRuntime } from "@/transfers/shared/base/BaseTransferRuntime.js"
import { UploadFileState } from "@/transfers/upload/UploadFileState.js"
import { attachmentType, uploadFileStatus, uploadState } from "@/transfers/upload/constants.js"


/**
 * Things to be added:
 * UploadRuntime receives register callback for everyone that wants to listen to the state change, including UploadStore
 *
 * UploadRuntime exposes callbacks like requestProducer start/end etc. to monitor each producer/consumer and know exactly when and if upload is finished
 *
 * Move away from watching uploadStore in uploader
 *
 * Figure a way for DiscordAttachmentConsumer to know when a file is finished.
 * Prob make UploadRuntime emit yet another callback, and make DiscordAttachmentConsumer
 * register one
 *
 */
export class UploadRuntime extends BaseTransferRuntime {
   constructor({ uploadFinishCallback }) {
      super({ initialState: uploadState.idle, runningState: uploadState.uploading, finishCallback: uploadFinishCallback })
      this.pendingWorkerFilesLength = 0

      this._emitGlobalState()
   }

   get uploadState() {
      return this.transferState //todo
   }

   setPendingWorkerFilesLength(number) {
      this.pendingWorkerFilesLength = number
      this._emitGlobalState()
   }

   toGlobalSnapshot() {
      this.estimator.update(this.getRemainingBytes())
      return {
         allBytesUploaded: this.allBytesTransfered,
         allBytesToUpload: this.allBytesToTransfer,
         uploadState: this.transferState,
         pendingWorkerFilesLength: this.pendingWorkerFilesLength,
         eta: this.estimator.getEta(),
         speed: this.estimator.getSpeed(),
         fileCount: this.fileStates.size
      }
   }

   /* =========================
    * Progress handling
    * ========================= */

   onUploadProgress(request, progressEvent) {
      const bytes = progressEvent.bytes
      if (!bytes || bytes <= 0) return

      this.allBytesTransfered += bytes

      const uploadedSoFar = progressEvent.bytes
      const totalSize = request.totalSize
      if (!totalSize || totalSize <= 0) return

      for (const attachment of request.attachments) {
         if (attachment.type !== attachmentType.file) continue

         const fileState = this.getFileState(attachment.fileObj.frontendId)
         const attachmentSize = attachment.rawBlob.size
         if (!attachmentSize || attachmentSize <= 0) continue

         const estimatedUploaded = Math.floor((attachmentSize / totalSize) * uploadedSoFar)

         fileState.updateTransferredBytes(estimatedUploaded)
      }
      this._emitGlobalState()
   }

   /* =========================
    * Retry / rollback handling
    * ========================= */

   fixUploadTracking(request, bytesUploaded) {
      this.allBytesTransfered = Math.max(0, this.allBytesTransfered - (bytesUploaded))
      const affectedFiles = this._collectAffectedFiles(request)

      for (const fileState of affectedFiles) {
         fileState.setStatus(uploadFileStatus.retrying)
         const newBytes = Math.max(0, fileState.bytesTransferred - bytesUploaded)
         fileState.setTransferredBytes(newBytes)
      }

      this._emitGlobalState()
   }

   finishExistingFile(frontendId) {
      const fileState = this.getFileState(frontendId)
      if (!fileState) return
      fileState.onDelete()
      return super.finishExistingFile(frontendId)
   }

   setUploadingState(state) {
      this.setTransferState(state) //todo
   }

   registerFile(file) {
      const frontendId = file.fileObj.frontendId

      if (this.fileStates.has(frontendId)) {
         throw new Error("Attempted to register file state of a file already registered")
      }

      const fileState = new UploadFileState(file, change => this._onRawFileFieldChange(change))

      this.fileStates.set(frontendId, fileState)
      fileState.emitInitialState()

      this._emitGlobalState()

      return fileState
   }

   cleanup() {
      super.cleanup()
      this.pendingWorkerFilesLength = 0
   }

   /* =========================
    * Helpers
    * ========================= */

   _collectAffectedFiles(request) {
      const map = new Map()

      for (const attachment of request.attachments) {
         const frontendId = attachment.fileObj.frontendId

         if (!map.has(frontendId)) {
            const fileState = this.fileStates.get(frontendId)

            if (!fileState) {
               throw new Error(`FileState not registered: ${frontendId}`)
            }

            map.set(frontendId, fileState)
         }
      }

      return Array.from(map.values())
   }
}