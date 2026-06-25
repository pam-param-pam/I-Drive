import { InternetProbe } from "@/transfers/shared/InternetProbe.js"
import { DownloadConsumer } from "@/transfers/downloads/downloadConsumer.js"
import { downloadState } from "@/transfers/downloads/constants.js"
import { DownloadRuntime } from "@/transfers/downloads/DownloadRuntime.js"
import { useTransferStore } from "@/stores/transferStore.js"
import { AsyncQueue } from "@/transfers/shared/AsyncQueue.js"
import { showToast } from "@/utils/common.js"

export class Downloader {
   constructor() {
      this.transferStore = useTransferStore()
      this.downloadQueue = new AsyncQueue()
      this.downloadConsumer = null
      this.downloadRuntime = null

      this.internetProbe = new InternetProbe({
         onRestored: () => this.onInternetRestored()
      })
   }

   initRuntimeUpload() {
      if (this.downloadRuntime) return

      this.downloadRuntime = new DownloadRuntime({ downloadFinishCallback: () => this.onDownloadSessionFinished() })

      this.downloadRuntime.onGlobalStateChange(snapshot => {
         this.transferStore.onDownloadGlobalStateChange(snapshot)
      })

      this.downloadRuntime.onFileChange(["status", "progress", "error", "fileObj"], ({ frontendId, field, current }) => {
         this.transferStore.updateDownloadFileField(frontendId, field, current)
      })

      this.downloadRuntime.onFileFinished(frontendId => {
         this.transferStore.onDownloadFileSaved(frontendId)
      })

      this.downloadRuntime.onTransferStateChange((newState, prevState) => {
         if (newState === downloadState.noInternet) {
            this.internetProbe.start()
         } else if (prevState === downloadState.noInternet) {
            this.internetProbe.stop()
         }
      })
   }

   async downloadFile(file) {
      this.checkIfSupported()
      this.initRuntimeUpload()

      if (this.downloadRuntime.getFileState(file.id)) {
         showToast("info", "toasts.fileAlreadyDownloading")
         return
      }

      const fileHandle = await this.getDownloadFileHandle(file)

      this.ensureQueue()
      this.downloadQueue.open()
      this.downloadRuntime.registerFile(file)

      await this.downloadQueue.put({
         file,
         offset: 0,
         fileHandle
      })

      this.startConsumer()

      if (this.downloadRuntime.downloadState === downloadState.idle) {
         this.downloadRuntime.setTransferState(downloadState.downloading)
      }
   }

   checkIfSupported() {
      if (typeof window.showSaveFilePicker !== "function") {
         throw new Error("This browser does not support direct file writing")
      }
   }

   async getDownloadFileHandle(file) {
      if (file.fileHandle) {
         return file.fileHandle
      }

      if (file.directoryHandle) {
         file.fileHandle = await file.directoryHandle.getFileHandle(file.name, { create: true })
         return file.fileHandle
      }

      file.fileHandle = await window.showSaveFilePicker({
         suggestedName: file.name
      })

      return file.fileHandle
   }

   startConsumer() {
      if (!this.downloadConsumer) {
         this.downloadConsumer = new DownloadConsumer({
            downloadQueue: this.downloadQueue,
            downloadRuntime: this.downloadRuntime
         })
      }

      if (!this.downloadConsumer.isRunning()) {
         this.downloadConsumer.run()
            .catch(err => {
               console.error("DownloadConsumer crashed", err)
               this.downloadRuntime.setTransferState(downloadState.error)
            })
      }
   }

   pauseAll() {
      if (this.downloadRuntime.downloadState !== downloadState.downloading) return
      this.downloadRuntime.setTransferState(downloadState.paused)
      this.downloadConsumer.pauseActiveDownload()
   }

   resumeAll() {
      if (this.downloadRuntime.downloadState !== downloadState.paused) return
      this.downloadRuntime.setTransferState(downloadState.downloading)
   }

   dismissFile(frontendId) {
      console.log("dismissing file: " + frontendId)
      this.downloadRuntime.finishExistingFile(frontendId)
   }
   retryFile(frontendId) {
      console.log("retrying file: " + frontendId)
      this.downloadConsumer.retryFile(frontendId)
   }

   onInternetRestored() {
      if (this.downloadRuntime.downloadState !== downloadState.noInternet) return

      this.internetProbe.stop()
      this.downloadRuntime.setTransferState(downloadState.downloading)
   }

   async cleanup() {
      console.log("cleanup called in downloader")
      await this.shutdown({ abort: false })
   }

   async abortAll() {
      if (this.downloadRuntime.downloadState === downloadState.aborting) return

      this.downloadRuntime.setTransferState(downloadState.aborting)
      await this.shutdown({ abort: true })
   }

   async shutdown({ abort }) {
      this.internetProbe.stop()

      if (this.downloadConsumer) {
         const downloadConsumer = this.downloadConsumer
         this.downloadConsumer = null

         if (abort) {
            await downloadConsumer.kill()
         } else {
            console.log(11111111)
            await downloadConsumer.stop()
            console.log(22222222)
         }
      }

      if (this.downloadQueue) {
         if (abort) {
            this.downloadQueue.clear()
         }
         this.downloadQueue.close()
      }

      this.downloadRuntime = null
      this.transferStore.cleanupDownload()

      if (abort) {
         showToast("success", "toasts.downloadAborted")
      }
   }

   ensureQueue() {
      if (this.downloadQueue) return
      this.downloadQueue = new AsyncQueue()
   }

   async onDownloadSessionFinished() {
      this.cleanup().then(() => {
         console.log("onDownloadSessionFinished + cleanup then")
         showToast("success", "toasts.downloadFinished")
      })
   }
}

let _downloaderInstance = null


export function getDownloader() {
   if (!_downloaderInstance) {
      _downloaderInstance = new Downloader()
   }
   return _downloaderInstance
}