import { AsyncQueue } from "@/transfers/upload/AsyncQueue.js"
import { InternetProbe } from "@/transfers/shared/InternetProbe.js"
import { DownloadConsumer } from "@/transfers/downloads/downloadConsumer.js"
import { downloadState } from "@/transfers/downloads/constants.js"
import { DownloadRuntime } from "@/transfers/downloads/DownloadRuntime.js"
import { useTransferStore } from "@/stores/transferStore.js"
import { uploadState } from "@/transfers/upload/constants.js"

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

      this.downloadRuntime = new DownloadRuntime({ uploadFinishCallback: this.onDownloadSessionFinished })

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
         if (newState === uploadState.noInternet) {
            this.internetProbe.start()
         } else if (prevState === uploadState.noInternet) {
            this.internetProbe.stop()
         }
      })
   }
   async downloadFile(file) {
      this.ensureQueue()
      this.initRuntimeUpload()
      this.downloadQueue.open()
      this.downloadRuntime.registerFile(file)

      await this.downloadQueue.put(file)

      this.startConsumer()

      if (this.downloadRuntime.downloadState !== downloadState.downloading) {
         this.downloadRuntime.setTransferState(downloadState.downloading)
      }
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
      this.downloadConsumer?.pauseActiveDownload()
   }

   resumeAll() {
      if (this.downloadRuntime.downloadState !== downloadState.paused) return

      this.downloadRuntime.setTransferState(downloadState.downloading)
      this.downloadConsumer?.resumeActiveDownload()
   }

   onInternetRestored() {
      if (this.downloadRuntime.downloadState !== downloadState.noInternet) return

      this.internetProbe.stop()
      this.downloadRuntime.setTransferState(downloadState.downloading)
      this.downloadConsumer?.resumeActiveDownload()
   }

   async cleanup() {
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
            await downloadConsumer.stop()
         }
      }

      if (this.downloadQueue) {
         if (abort) {
            this.downloadQueue.clear?.()
         }

         this.downloadQueue.close()
      }

      this.downloadRuntime.cleanup()
   }

   ensureQueue() {
      if (this.downloadQueue) return
      this.downloadQueue = new AsyncQueue()
   }
   onDownloadSessionFinished() {

   }
}

let _downloaderInstance = null

export function getDownloader() {
   if (!_downloaderInstance) {
      _downloaderInstance = new Downloader()
   }
   return _downloaderInstance
}