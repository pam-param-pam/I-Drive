import { UploadEstimator } from "@/upload/UploadEstimator.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { attachmentType, fileUploadStatus, uploadState } from "@/utils/constants.js"
import { FileStateHolder } from "@/upload/FileStateHolder.js"

export class UploadRuntime {
   constructor({uploadFinishCallback}) {
      this.fileStates = new Map()
      this.uploadStore = useUploadStore()
      this.estimator = new UploadEstimator()

      this.uploadSpeedMap = new Map()
      this.allBytesUploaded = 0
      this.allBytesToUpload = 0
      this._uploadFinishCallback = uploadFinishCallback
      this.uploadState = uploadState.idle
      this.pendingWorkerFilesLength = 0

      this._emitGlobalState()
   }

   /* =========================
    * Progress handling
    * ========================= */

   onUploadProgress(request, progressEvent) {
      const bytes = progressEvent.bytes
      if (!bytes || bytes <= 0) return

      this.allBytesUploaded += bytes
      this.uploadSpeedMap.set(request.id, progressEvent.rate)

      const uploadedSoFar = progressEvent.bytes
      const totalSize = request.totalSize
      if (!totalSize || totalSize <= 0) return

      for (const attachment of request.attachments) {
         if (attachment.type !== attachmentType.file) continue

         const fileState = this.getFileState(attachment.fileObj.frontendId)
         const attachmentSize = attachment.rawBlob.size
         if (!attachmentSize || attachmentSize <= 0) continue

         const estimatedUploaded = Math.floor(
            (attachmentSize / totalSize) * uploadedSoFar
         )

         fileState.updateUploadedBytes(estimatedUploaded)

         const percentage = fileState.progress
         if (percentage > 100) {
            console.warn(
               `Percentage overflow (${percentage}%) for file ${attachment.fileObj.name}`
            )
         }
      }
      this._emitGlobalState()
   }

   /* =========================
    * Retry / rollback handling
    * ========================= */

   fixUploadTracking(request, bytesUploaded) {
      this.uploadSpeedMap.delete(request.id)
      this.allBytesUploaded = Math.max(
         0,
         this.allBytesUploaded - (bytesUploaded || 0)
      )

      const affectedFiles = this._collectAffectedFiles(request)

      for (const fileState of affectedFiles) {
         this._setStatus(fileState.frontendId, fileUploadStatus.retrying)

         const newBytes = Math.max(
            0,
            fileState.uploadedBytes - bytesUploaded
         )
         fileState.setUploadedBytes(newBytes)
      }

      this._emitGlobalState()
   }

   fixMissingBytesFromRequest(request, missingBytes) {
      if (!missingBytes || missingBytes <= 0) return

      this.allBytesUploaded += missingBytes

      const affectedFiles = this._collectAffectedFiles(request)
      const perFileBytes = Math.floor(missingBytes / affectedFiles.length || 1)

      for (const fileState of affectedFiles) {
         fileState.updateUploadedBytes(perFileBytes)
      }

      this._emitGlobalState()
   }

   markRequestFinished(request) {
      this.uploadSpeedMap.delete(request.id)
      this._emitGlobalState()
   }

   markFileSaved(frontendId) {
      this.fileStates.delete(frontendId)
      this.uploadStore.deleteFileState(frontendId)
      this._checkAllFilesFinished()
   }

   setAllBytesToUpload(bytes) {
      this.allBytesToUpload = bytes
   }

   setUploadingState(state) {
      this.uploadState = state
      this._emitGlobalState()
   }

   setPendingWorkerFilesLength(number) {
      this.pendingWorkerFilesLength = number
      this._emitGlobalState()
   }
   registerFile(file) {
      const frontendId = file.fileObj.frontendId

      if (this.fileStates.has(frontendId)) {
         throw Error("Attempted to register file state of a file already registered")
      }

      const _notifyCallback = (snapshot) => {
         this.uploadStore.updateFile(frontendId, snapshot)
      }

      const fileState = new FileStateHolder(file, _notifyCallback)

      this.fileStates.set(frontendId, fileState)
      this._emitGlobalState()

      this.uploadStore.registerFile(fileState.toStoreSnapshot())
   }

   getFileState(frontendId) {
      let state = this.fileStates.get(frontendId)
      if (!state) {
         console.warn("Couldn't find file state for: " + frontendId)
      }
      return state
   }

   /* =========================
    * Helpers
    * ========================= */

   _getRemainingBytes() {
      return this.allBytesToUpload - this.allBytesUploaded
   }

   _emitGlobalState() {
      this.uploadStore.setAllBytesUploaded(this.allBytesUploaded)
      this.uploadStore.setAllBytesToUpload(this.allBytesToUpload)
      this.uploadStore.setState(this.uploadState)
      this.uploadStore.setPendingWorkerFilesLength(this.pendingWorkerFilesLength)

      const speed = this._computeSpeed()
      this.uploadStore.setUploadSpeed(speed)
      this.estimator.updateSpeed(speed)

      const remainingBytes = this._getRemainingBytes()
      const eta = this.estimator.estimateRemainingTime(remainingBytes)
      this.uploadStore.setEta(eta)
   }

   isUploadFullyFinished() {
      return this.fileStates.size === 0
   }
   _checkAllFilesFinished() {
      if (this.isUploadFullyFinished() && this._uploadFinishCallback) {
         this._uploadFinishCallback()
      }
   }

   _computeSpeed() {
      let total = 0
      for (const rate of this.uploadSpeedMap.values()) {
         total += rate
      }
      return total
   }

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

   _setStatus(frontendId, status) {
      this.fileStates.get(frontendId).setStatus(status)
   }


}
