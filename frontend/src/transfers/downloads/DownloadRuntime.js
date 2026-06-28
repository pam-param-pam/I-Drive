import { DownloadFileState } from "@/transfers/downloads/DownloadFileState.js"
import { downloadState } from "@/transfers/downloads/constants.js"
import { BaseTransferRuntime } from "@/transfers/shared/base/BaseTransferRuntime.js"

export class DownloadRuntime extends BaseTransferRuntime {
   constructor({ downloadFinishCallback } = {}) {
      super({ initialState: downloadState.idle, runningState: downloadState.downloading, finishCallback: downloadFinishCallback })
      this._emitGlobalState()
   }

   get downloadState() {
      return this.transferState
   }

   toGlobalSnapshot() {
      this.estimator.update(this.getRemainingBytes())

      return {
         allBytesDownloaded: this.allBytesTransfered,
         allBytesToDownload: this.allBytesToTransfer,
         downloadState: this.downloadState,
         eta: this.estimator.getEta(),
         speed: this.estimator.getSpeed(),
         fileCount: this.fileStates.size
      }
   }

   registerFile(file) {
      const frontendId = file.id

      if (this.fileStates.has(frontendId)) {
         throw new Error("Attempted to register download file state of a file already registered")
      }

      const fileState = new DownloadFileState(file, change => this._onRawFileFieldChange(change))
      this.fileStates.set(frontendId, fileState)
      this.updateAllBytesToTransfer(file.size)

      fileState.emitInitialState()
      this._emitGlobalState()

      return fileState
   }

   onDownloadProgress(fileId, progressEvent) {
      const fileState = this.getFileState(fileId)

      const prevDownloadedBytes = fileState.bytesTransferred

      fileState.onDownloadProgress(progressEvent)

      const delta = Math.max(0, fileState.bytesTransferred - prevDownloadedBytes)

      this.allBytesTransfered += delta

      this._emitGlobalState()
   }
}