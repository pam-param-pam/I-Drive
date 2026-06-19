import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { useUploadStore } from "@/stores/uploadStore.js"
import { uploadState, uploadType } from "@/utils/constants.js"
import { canUpload } from "@/api/user.js"
import { UploadRuntime } from "@/transfers/upload/UploadRuntime.js"
import { showToast } from "@/utils/common.js"
import { checkFileDepth, checkFilesSizes } from "@/transfers/upload/utils/uploadHelper.js"
import { watch } from "vue"
import { UploadQueues } from "@/transfers/upload/UploadQueues.js"
import { DiscordUploadPool } from "@/transfers/upload/DiscordUploadPool.js"
import { DiscordResponseStage } from "@/transfers/upload/workers/DiscordResponseStage.js"
import { BackendFileConsumer } from "@/transfers/upload/workers/BackendFileConsumer.js"
import { RequestProducer } from "@/transfers/upload/workers/RequestProducer.js"
import { InternetProbe } from "@/transfers/shared/InternetProbe.js"
import { beforeUnloadEvent } from "@/transfers/shared/helper.js"

/*
FileProcessorWorker
   -> fileQueue
      -> RequestProducer
         -> requestQueue
            -> DiscordUploadConsumer x N
               -> discordResponseQueue
                  -> DiscordResponseConsumer
                     -> backendFileQueue
                        -> BackendFileConsumer
*/

export class Uploader {
   constructor() {
      this.mainStore = useMainStore()
      this.uploadStore = useUploadStore()

      this.uploadRuntime = null
      this.queues = null

      this.fileProcessorWorker = null

      this.requestProducer = null
      this.uploadPool = null
      this.discordResponseConsumer = null
      this.backendFileConsumer = null

      this.internetProbe = new InternetProbe({
         onRestored: () => this._onInternetRestored() //todo
      })

      watch(
         () => this.mainStore.settings.concurrentUploadRequests,
         value => this.setUploadConcurrency(value)
      )

      this.startQueueStatsLogging()
   }

   startQueueStatsLogging() {
      if (this._logInterval) return

      this._logInterval = setInterval(() => {
         this.logQueueStats()
      }, 1000)
   }

   stopQueueStatsLogging() {
      if (!this._logInterval) return

      clearInterval(this._logInterval)
      this._logInterval = null
   }

   logQueueStats() {
      if (!this.queues) return

      this.queues.logStats()
   }

   async startUploadWithChecks(type, folderContext, filesList) {
      const res = await canUpload(folderContext)
      if (!res.can_upload) return

      const maxFolderDepth = this.mainStore.config.maxFolderDepth
      const depth = await checkFileDepth(filesList, maxFolderDepth)

      if (depth) {
         showToast("error", "toasts.fileDepthTooBig", {}, { max: maxFolderDepth, current: depth })
         return
      }

      const proceed = async () => {
         await this.startUpload(type, folderContext, filesList, res.lockFrom)
      }

      if (await checkFilesSizes(filesList)) {
         this.mainStore.showHover({
            prompt: "notOptimizedForSmallFiles",
            confirm: proceed
         })
      } else {
         await proceed()
      }
   }

   async startUpload(type, folderContext, filesList, lockFrom) {
      this.initRuntimeUpload()
      this.initQueues()
      this.startConsumers()
      this.startProducer()

      if (this.uploadRuntime.uploadState === uploadState.idle) {
         this.uploadRuntime.setUploadingState(uploadState.uploading)
      }

      this.processNewFiles(type, folderContext, filesList, lockFrom)
   }

   initRuntimeUpload() {
      if (this.uploadRuntime) return

      this.uploadRuntime = new UploadRuntime({ uploadFinishCallback: this.onUploadSessionFinished })

      this.uploadRuntime.onGlobalStateChange(snapshot => {
         this.uploadStore.onGlobalStateChange(snapshot)
      })

      this.uploadRuntime.onFileChange(["status", "progress", "error", "fileObj", "frontendId"], ({ frontendId, field, current }) => {
         this.uploadStore.updateFileField(frontendId, field, current)
      })

      this.uploadRuntime.onFileSaved(frontendId => {
         this.uploadStore.onFileSaved(frontendId)
      })

      this.uploadRuntime.onUploadStateChange((newState, prevState) => {
         if (newState === uploadState.noInternet) {
            this.internetProbe.start()
         } else if (prevState === uploadState.noInternet) {
            this.internetProbe.stop()
         }
      })
   }

   initQueues() {
      if (!this.queues) {
         this.queues = new UploadQueues()
      } else {
         this.queues.openAll()
      }
   }

   startProducer() {
      if (!this.requestProducer) {
         this.requestProducer = new RequestProducer({
            uploadRuntime: this.uploadRuntime,
            fileQueue: this.queues.fileQueue,
            requestQueue: this.queues.requestQueue,
            requestMoreFiles: this.requestMoreFiles.bind(this)
         })
      }

      if (!this.requestProducer.isRunning()) {
         this.requestProducer.run().catch(err => {
            console.error("RequestProducer crashed", err)
            this.uploadStore.state = uploadState.error
         })
      }
   }

   startConsumers() {
      this.startUploadPool()
      this.startDiscordResponseConsumer()
      this.startBackendFileConsumer()
   }

   startUploadPool() {
      if (!this.uploadPool) {
         this.uploadPool = new DiscordUploadPool({
            requestQueue: this.queues.requestQueue,
            discordResponseQueue: this.queues.discordResponseQueue,
            uploadRuntime: this.uploadRuntime,
            uploadStore: this.uploadStore
         })
      }

      this.uploadPool.setConcurrency(this.mainStore.settings.concurrentUploadRequests)
   }

   startDiscordResponseConsumer() {
      if (!this.discordResponseConsumer) {
         console.info("Creating discordResponseConsumer!")
         this.discordResponseConsumer = new DiscordResponseStage({
            discordResponseQueue: this.queues.discordResponseQueue,
            backendFileQueue: this.queues.backendFileQueue,
            uploadRuntime: this.uploadRuntime
         })
      }

      if (!this.discordResponseConsumer.isRunning()) {
         console.info("Starting discordResponseConsumer!")
         this.discordResponseConsumer.run().catch(err => {
            console.error("DiscordResponseConsumer crashed", err)
            this.uploadStore.state = uploadState.error
         })
      }
   }

   startBackendFileConsumer() {
      if (!this.backendFileConsumer) {
         console.info("Creating backendFileConsumer!")
         this.backendFileConsumer = new BackendFileConsumer({
            backendFileQueue: this.queues.backendFileQueue,
            uploadRuntime: this.uploadRuntime
         })
      }

      if (!this.backendFileConsumer.isRunning()) {
         console.info("Starting backendFileConsumer!")
         this.backendFileConsumer.run().catch(err => {
            console.error("BackendFileConsumer crashed", err)
            this.uploadStore.state = uploadState.error
         })
      }
   }

   setUploadConcurrency(target) {
      this.uploadPool?.setConcurrency(target)
   }

   ensureQueuesOpen() {
      this.queues?.openAll()
   }

   processNewFiles(typeOfUpload, folderContext, filesList, lockFrom) {
      const uploadId = uuidv4()
      const encryptionMethod = this.mainStore.settings.encryptionMethod
      const parentPassword = this.mainStore.getFolderPassword(lockFrom)

      this.ensureFileProcessorWorker()

      this.uploadRuntime.setPendingWorkerFilesLength(this.uploadRuntime.pendingWorkerFilesLength + filesList.length)
      this.uploadRuntime.setAllBytesToUpload(this.uploadRuntime.allBytesToUpload + this.calculateTotalBytes(typeOfUpload, filesList))

      this.fileProcessorWorker.postMessage({
         type: "init",
         typeOfUpload,
         folderContext,
         filesList,
         uploadId,
         encryptionMethod,
         parentPassword,
         lockFrom
      })

      this.requestMoreFiles()
   }

   ensureFileProcessorWorker() {
      if (this.fileProcessorWorker) return

      this.fileProcessorWorker = new Worker(new URL("../../workers/fileProcessorWorker.js", import.meta.url), { type: "module" })

      this.fileProcessorWorker.onmessage = async event => {
         const { files, done } = event.data

         if (!done) {
            this.initQueues()
            this.startConsumers()
            this.startProducer()
         }

         if (files?.length) {
            for (const file of files) {
               this.uploadRuntime.registerFile(file)
               this.uploadRuntime.setPendingWorkerFilesLength(this.uploadRuntime.pendingWorkerFilesLength - 1)
               await this.queues.fileQueue.put(file)
            }
         }

         if (done) {
            this.queues.fileQueue.close()
         }
      }
   }

   calculateTotalBytes(typeOfUpload, filesList) {
      let totalBytes = 0

      for (const item of filesList) {
         if (typeOfUpload === uploadType.dragAndDropInput) {
            totalBytes += item.file.size
         } else {
            totalBytes += item.size
         }
      }

      return totalBytes
   }

   requestMoreFiles() {
      this.fileProcessorWorker.postMessage({ type: "produce" })
   }

   pauseAll() {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return

      this.uploadRuntime.setUploadingState(uploadState.paused)
      this.queues.requestQueue.open()
      this.uploadPool.abortAllUploadRequests()
      //yes we technically should close the queue if needed (if we indeed had just opened it but oh well)
   }

   resumeAll() {
      if (this.uploadRuntime.uploadState !== uploadState.paused) return

      this.uploadRuntime.setUploadingState(uploadState.uploading)
   }

   retrySaveFailedFiles() {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return
      //here we must only open the needed queues

      this.queues.backendFileQueue.open()
      this.backendFileConsumer.retryFailedFiles().then(() => {
         this.startBackendFileConsumer()
         this.queues.backendFileQueue.close()
      })
   }

   retryFailedRequests() {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return

      this.ensureQueuesOpen()
      this.uploadPool.retryFailedRequests().then(() => {
         this.startConsumers()
         this.queues.fileQueue.close()
         this.queues.requestQueue.close()
      })
   }

   retryGoneFile(frontendId) {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return

      this.ensureQueuesOpen()
      let file = this.requestProducer.getGoneFile(frontendId)
      this.queues.fileQueue.put(file).then(() => {
         this.startConsumers()
         this.startProducer()
         this.queues.fileQueue.close()
      })
   }

   dismissFile(frontendId) {
      this.uploadRuntime.deleteFileState(frontendId)
   }

   onUploadSessionFinished = () => {
      this.cleanup().then(() => {
         showToast("success", "toasts.uploadFinished")
      })
   }

   async cleanup() {
      window.removeEventListener("beforeunload", beforeUnloadEvent)

      if (this.uploadPool) {
         await this.uploadPool.stopAll()
         this.uploadPool = null
      }

      if (this.discordResponseConsumer) {
         await this.discordResponseConsumer.stop()
         this.discordResponseConsumer = null
      }

      if (this.backendFileConsumer) {
         await this.backendFileConsumer.stop()
         this.backendFileConsumer = null
      }

      if (this.requestProducer) {
         await this.requestProducer.stop()
         this.requestProducer = null
      }

      if (this.queues) {
         this.queues.closeAll()
         this.queues = null
      }

      if (this.fileProcessorWorker) {
         this.fileProcessorWorker.postMessage({ type: "reset" })
         this.fileProcessorWorker = null
      }

      this.internetProbe.stop()
      this.stopQueueStatsLogging()

      this.uploadRuntime = null
      this.uploadStore.cleanup()
   }

   async abortAll() {
      if (this.uploadRuntime.uploadState === uploadState.aborting) return
      this.uploadRuntime.setUploadingState(uploadState.aborting)
      await this.backendFileConsumer.saveFilesIfNeeded()

      window.removeEventListener("beforeunload", beforeUnloadEvent)

      if (this.uploadPool) {
         await this.uploadPool.killAll()
         this.uploadPool = null
      }

      if (this.discordResponseConsumer) {
         await this.discordResponseConsumer.kill()
         this.discordResponseConsumer = null
      }

      if (this.backendFileConsumer) {
         await this.backendFileConsumer.kill()
         this.backendFileConsumer = null
      }

      if (this.requestProducer) {
         await this.requestProducer.kill()
         this.requestProducer = null
      }

      if (this.queues) {
         this.queues.closeAll()
         this.queues = null
      }

      if (this.fileProcessorWorker) {
         this.fileProcessorWorker.terminate()
         this.fileProcessorWorker = null
      }

      this.internetProbe.stop()
      this.stopQueueStatsLogging()

      this.uploadRuntime = null
      this.uploadStore.cleanup()
      showToast("success", "toasts.uploadAborted")
   }

   _onInternetRestored() {
      if (this.uploadRuntime?.uploadState !== uploadState.noInternet) return
      this.uploadRuntime.setUploadingState(uploadState.uploading)
   }
}

let _uploaderInstance = null

export function getUploader() {
   if (!_uploaderInstance) {
      _uploaderInstance = new Uploader()
   }
   return _uploaderInstance
}
