import { InternetProbe } from "@/transfers/shared/InternetProbe.js"
import { downloadState } from "@/transfers/downloads/constants.js"
import { DownloadRuntime } from "@/transfers/downloads/DownloadRuntime.js"
import { useTransferStore } from "@/stores/transferStore.js"
import { AsyncQueue } from "@/transfers/shared/AsyncQueue.js"
import { showToast } from "@/utils/common.js"
import { FileConsumer } from "@/transfers/downloads/workers/fileConsumer.js"
import { ZipConsumer } from "@/transfers/downloads/workers/zipConsumer.js"
import { createZIP } from "@/api/item.js"
import { backendInstance } from "@/axios/networker.js"
import { createShareZIP } from "@/api/share.js"
import { FilePickerNotSupported } from "@/transfers/downloads/utils/helper.js"

export class Downloader {
   constructor() {
      this.transferStore = useTransferStore()

      this.fileQueue = new AsyncQueue()
      this.zipQueue = new AsyncQueue()

      this.fileConsumer = null
      this.zipConsumer = null
      this.downloadRuntime = null

      this.internetProbe = new InternetProbe({
         onRestored: () => this.onInternetRestored()
      })
   }

   initRuntimeDownload() {
      if (this.downloadRuntime) return

      this.downloadRuntime = new DownloadRuntime({
         downloadFinishCallback: () => this.onDownloadSessionFinished()
      })

      this.downloadRuntime.onGlobalStateChange(snapshot => {
         this.transferStore.onDownloadGlobalStateChange(snapshot)
      })

      this.downloadRuntime.onFileChange(["status", "progress", "error", "fileObj", "bytesTransferred", "size"], ({ frontendId, field, current }) => {
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
      this.initRuntimeDownload()

      if (this.downloadRuntime.getFileState(file.id)) {
         showToast("info", "toasts.fileAlreadyDownloading")
         return
      }

      let fileHandle = await this.getDownloadFileHandle(file)

      this.ensureFileQueue()
      this.fileQueue.open()

      this.downloadRuntime.registerFile(file)

      await this.fileQueue.put({
         file,
         offset: 0,
         fileHandle
      })

      this.startFileConsumer()
      this.ensureDownloadingState()
   }

   async downloadZip(ids, shareToken) {
      this.checkIfSupported()
      this.initRuntimeDownload()

      const zipDescriptor = shareToken ? await createShareZIP(shareToken, { ids }) : await createZIP({ ids })
      let zipFile = await this.prepareZipFile(zipDescriptor)

      let fileHandle = await this.getZipFileHandle(zipFile)

      this.ensureZipQueue()
      this.zipQueue.open()

      this.downloadRuntime.registerFile(zipFile)

      await this.zipQueue.put({
         file: zipFile,
         offset: 0,
         fileHandle
      })

      this.startZipConsumer()
      this.ensureDownloadingState()
   }

   async prepareZipFile(zipDescriptor) {
      const id = zipDescriptor.id
      const name = zipDescriptor.name + ".zip"
      const downloadUrl = zipDescriptor.download_url + "?&raw=True"

      const response = await backendInstance.get(downloadUrl, {
         headers: {
            Range: "bytes=0-0"
         },
         baseURL: ""
      })

      const contentRange = response.headers.get("content-range")
      let size =  Number(contentRange.split("/")[1])
      return {
         id: `zip:${id}`,
         zipId: id,
         name,
         size,
         downloadUrl,
         fileHandle: null,
         isZip: true
      }
   }

   async getZipFileHandle(zipFile) {
      zipFile.fileHandle = await window.showSaveFilePicker({
         suggestedName: zipFile.name
      })

      return zipFile.fileHandle
   }

   checkIfSupported() {
      if (typeof window.showSaveFilePicker !== "function") {
         throw new FilePickerNotSupported()
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

   startFileConsumer() {
      if (!this.fileConsumer) {
         this.fileConsumer = new FileConsumer({
            fileQueue: this.fileQueue,
            downloadRuntime: this.downloadRuntime
         })
      }

      if (!this.fileConsumer.isRunning()) {
         this.fileConsumer.run()
            .catch(err => {
               console.error("FileConsumer crashed", err)
               this.downloadRuntime?.setTransferState(downloadState.error)
            })
      }
   }

   startZipConsumer() {
      if (!this.zipConsumer) {
         this.zipConsumer = new ZipConsumer({
            zipQueue: this.zipQueue,
            downloadRuntime: this.downloadRuntime
         })
      }

      if (!this.zipConsumer.isRunning()) {
         this.zipConsumer.run()
            .catch(err => {
               console.error("ZipConsumer crashed", err)
               this.downloadRuntime?.setTransferState(downloadState.error)
            })
      }
   }

   ensureDownloadingState() {
      if (this.downloadRuntime.transferState === downloadState.idle) {
         this.downloadRuntime.setTransferState(downloadState.downloading)
      }
   }

   pauseAll() {
      if (this.downloadRuntime.transferState !== downloadState.downloading) return

      this.downloadRuntime.setTransferState(downloadState.paused)

      this.fileConsumer?.pauseActiveDownload()
      this.zipConsumer?.pauseActiveDownload()
   }

   resumeAll() {
      if (this.downloadRuntime.transferState !== downloadState.paused) return

      this.downloadRuntime.setTransferState(downloadState.downloading)
   }

   dismissFile(frontendId) {
      this.downloadRuntime.finishExistingFile(frontendId)
   }

   async retryFile(frontendId) {
      if (await this.fileConsumer?.retryFile(frontendId)) {
         this.startFileConsumer()
         this.ensureDownloadingState()
         return
      }

      if (await this.zipConsumer?.retryFile(frontendId)) {
         this.startZipConsumer()
         this.ensureDownloadingState()
      }
   }

   onInternetRestored() {
      if (this.downloadRuntime.transferState !== downloadState.noInternet) return

      this.internetProbe.stop()
      this.downloadRuntime.setTransferState(downloadState.downloading)
   }

   async cleanup() {
      await this.shutdown({ abort: false })
   }

   async abortAll() {
      if (this.downloadRuntime.transferState === downloadState.aborting) return

      this.downloadRuntime.setTransferState(downloadState.aborting)
      await this.shutdown({ abort: true })
   }

   async shutdown({ abort }) {
      this.internetProbe.stop()

      if (this.fileConsumer) {
         const fileConsumer = this.fileConsumer
         this.fileConsumer = null

         if (abort) {
            await fileConsumer.kill()
         } else {
            await fileConsumer.stop()
         }
      }

      if (this.zipConsumer) {
         const zipConsumer = this.zipConsumer
         this.zipConsumer = null

         if (abort) {
            await zipConsumer.kill()
         } else {
            await zipConsumer.stop()
         }
      }

      if (this.fileQueue) {
         if (abort) {
            this.fileQueue.clear()
         }

         this.fileQueue.close()
      }

      if (this.zipQueue) {
         if (abort) {
            this.zipQueue.clear()
         }

         this.zipQueue.close()
      }

      this.downloadRuntime = null
      this.transferStore.cleanupDownload()

      if (abort) {
         showToast("success", "toasts.downloadAborted")
      }
   }

   ensureFileQueue() {
      if (this.fileQueue) return
      this.fileQueue = new AsyncQueue()
   }

   ensureZipQueue() {
      if (this.zipQueue) return
      this.zipQueue = new AsyncQueue()
   }

   async onDownloadSessionFinished() {
      this.cleanup().then(() => {
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