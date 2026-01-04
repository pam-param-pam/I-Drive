import { UploadEstimator } from "@/upload/UploadEstimator.js"
import { attachmentType, fileUploadStatus, uploadState } from "@/utils/constants.js"
import { FileStateHolder } from "@/upload/FileStateHolder.js"


/**
 * Things to be added:
 * UploadRuntime receives register callback for everyone that wants to listen to the state change, including UploadStore
 *
 * UploadRuntime exposes callbacks like requestProducer start/end etc to monitor each producer/consumer and know exactly when and if upload is finished
 *
 * Move away from watching uploadStore in uploader
 *
 * Figure a way for DiscordAttachmentConsumer to know when a file is finished. Prob make UploadRuntime emit a yet another callback, and make DiscordAttachmentConsumer
 * register one
 *
 * 
 */
export class UploadRuntime {
   constructor({ uploadFinishCallback }) {
      this.fileStates = new Map()
      this.estimator = new UploadEstimator()

      this.allBytesUploaded = 0
      this.allBytesToUpload = 0
      this._uploadFinishCallback = uploadFinishCallback
      this.uploadState = uploadState.idle
      this.pendingWorkerFilesLength = 0

      // Listener groups
      this._globalStateListeners = new Set()
      this._uploadStateListeners = new Set()
      this._fileSavedListeners = new Set()

      this._fileChangeSubscriptions = new Set()

      this._emitGlobalState()
   }
   onFileChange(fields, listener) {
      if (!Array.isArray(fields) || fields.length === 0) {
         throw new Error("onFileChange requires a non-empty field list")
      }

      const fieldSet = new Set(fields)

      // // validation stays here
      // for (const f of fieldSet) {
      //    if (!this._isKnownFileField(f)) {
      //       throw new Error(`Unknown file field: ${f}`)
      //    }
      // }

      const sub = { fields: fieldSet, listener }
      this._fileChangeSubscriptions.add(sub)

      return () => this._fileChangeSubscriptions.delete(sub)
   }

   toGlobalSnapshot() {
      return {
         allBytesUploaded: this.allBytesUploaded,
         allBytesToUpload: this.allBytesToUpload,
         uploadState: this.uploadState,
         pendingWorkerFilesLength: this.pendingWorkerFilesLength,
         eta: this.estimator.estimateRemainingTime(this._getRemainingBytes()),
         speed: this.estimator.getSpeed(),
         fileCount: this.fileStates.size
      }
   }
   onGlobalStateChange(listener) {
      this._globalStateListeners.add(listener)
      return () => this._globalStateListeners.delete(listener)
   }

   onUploadStateChange(listener) {
      this._uploadStateListeners.add(listener)
      return () => this._uploadStateListeners.delete(listener)
   }

   onFileSaved(listener) {
      this._fileSavedListeners.add(listener)
      return () => this._fileSavedListeners.delete(listener)
   }

   _emitGlobalState() {
      const snapshot = this.toGlobalSnapshot()
      for (const l of this._globalStateListeners) {
         l(snapshot)
      }
   }

   _emitUploadState(state) {
      for (const l of this._uploadStateListeners) {
         l(state)
      }
   }

   _emitFileSaved(frontendId) {
      for (const l of this._fileSavedListeners) {
         l(frontendId)
      }
   }


   /* =========================
    * Progress handling
    * ========================= */

   onUploadProgress(request, progressEvent) {
      const bytes = progressEvent.bytes
      if (!bytes || bytes <= 0) return

      this.allBytesUploaded += bytes

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
      this.allBytesUploaded = Math.max(0, this.allBytesUploaded - (bytesUploaded || 0))
      const affectedFiles = this._collectAffectedFiles(request)

      for (const fileState of affectedFiles) {
         this._setStatus(fileState.frontendId, fileUploadStatus.retrying)
         const newBytes = Math.max(0,fileState.uploadedBytes - bytesUploaded)
         fileState.setUploadedBytes(newBytes)
      }

      this._emitGlobalState()
   }

   markFileSaved(frontendId) {
      this.getFileState(frontendId).onDelete()
      this.fileStates.delete(frontendId)
      this._emitFileSaved(frontendId)
      this._checkAllFilesFinished()
   }

   setAllBytesToUpload(bytes) {
      this.allBytesToUpload = bytes
   }

   setUploadingState(state) {
      if (this.uploadState === state) return
      this.uploadState = state
      this._emitUploadState(state)
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

      const fileState = new FileStateHolder(file,change => this._onRawFileFieldChange(change))
      this.fileStates.set(frontendId, fileState)
      fileState.emitInitialState()

      this._emitGlobalState() //todo
   }
   _onRawFileFieldChange(change) {
      const { frontendId, field } = change

      for (const sub of this._fileChangeSubscriptions) {
         if (sub.fields.has(field)) {
            sub.listener({
               frontendId,
               field,
               prev: change.prev,
               current: change.current
            })
         }
      }
   }

   getFileState(frontendId) {
      let state = this.fileStates.get(frontendId)
      if (!state) {
         console.warn("Couldn't find file state for: " + frontendId)
      }
      return state
   }
   deleteFileState(frontendId) {
      this.markFileSaved(frontendId)
   }

   /* =========================
    * Helpers
    * ========================= */

   _getRemainingBytes() {
      return this.allBytesToUpload - this.allBytesUploaded
   }

   isUploadFullyFinished() {
      return this.fileStates.size === 0
   }
   _checkAllFilesFinished() {
      if (this.isUploadFullyFinished() && this._uploadFinishCallback) {
         this._uploadFinishCallback()
      }
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
   async waitUntilResumed() {
      return new Promise(resolve => {
         const unsubscribe = this.onUploadStateChange(
            (newState) => {
               if (newState === uploadState.uploading) {
                  unsubscribe()
                  resolve()
               }
            }
         )
      })
   }

}
