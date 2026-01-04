import { useMainStore } from "@/stores/mainStore.js"
import { v4 as uuidv4 } from "uuid"
import { useUploadStore } from "@/stores/uploadStore.js"
import { uploadState, uploadType } from "@/utils/constants.js"
import { canUpload, checkWifi } from "@/api/user.js"
import { AsyncQueue } from "@/upload/AsyncQueue.js"
import { RequestProducer } from "@/upload/RequestProducer.js"
import { DiscordUploadConsumer } from "@/upload/DiscordUploadConsumer.js"
import { UploadRuntime } from "@/upload/UploadRuntime.js"
import { showToast } from "@/utils/common.js"
import { checkFilesSizes } from "@/upload/utils/uploadHelper.js"
import { watch } from "vue"
import { DiscordResponseConsumer } from "@/upload/DiscordResponseConsumer.js"
import { BackendFileConsumer } from "@/upload/BackendFileConsumer.js"
import { DiscordAttachmentConsumer } from "@/upload/DiscordAttachmentConsumer.js"

export class Uploader {
   constructor() {
      this.mainStore = useMainStore()
      this.uploadStore = useUploadStore()

      this.uploadRuntime = null
      // queues
      this.fileQueue = null
      this.requestQueue = null
      this.discordResponseQueue = null
      this.backendFileQueue = null
      this.discordAttachmentQueue = null

      // workers
      this.fileProcessorWorker = null

      //consumers
      this.requestProducer = null
      this.discordResponseConsumer = null
      this.backendFileConsumer = null
      this.discordAttachmentConsumer = null
      this.uploadConsumers = []

      this._internetProbeInterval = null

      setInterval(() => this.logQueueStats(), 5000)

      watch(
         () => this.mainStore.settings.concurrentUploadRequests,
         value => this.setUploadConcurrency(value)
      )
   }

   logQueueStats() {
      console.log(
         "fileQueue:", this.fileQueue?.size(),
         "requestQueue:", this.requestQueue?.size(),
         "discordResponseQueue:", this.discordResponseQueue?.size(),
         "backendFileQueue", this.backendFileQueue?.size(),
         "discordAttachmentQueue", this.discordAttachmentQueue.size(),
      )
   }

   async startUploadWithChecks(type, folderContext, filesList) {
      const mainStore = useMainStore()

      const proceed = async () => {
         await this.startUpload(type, folderContext, filesList)
      }

      if (await checkFilesSizes(filesList)) {
         mainStore.showHover({
            prompt: "notOptimizedForSmallFiles",
            confirm: proceed
         })
      } else {
         await proceed()
      }
   }

   async startUpload(type, folderContext, filesList) {
      // window.addEventListener("beforeunload", beforeUnload)

      const res = await canUpload(folderContext)
      if (!res.can_upload) return

      this.initRuntimeUpload()
      this.initQueues()
      this.startConsumers()
      this.startProducer()

      if (this.uploadRuntime.uploadState === uploadState.idle) {
         this.uploadRuntime.setUploadingState(uploadState.uploading)

      }
      this.processNewFiles(type, folderContext, filesList, res.lockFrom)
   }

   processNewFiles(typeOfUpload, folderContext, filesList, lockFrom) {
      const uploadId = uuidv4()
      const encryptionMethod = this.mainStore.settings.encryptionMethod
      const parentPassword = this.mainStore.getFolderPassword(lockFrom)

      this.workerDone = false
      if (!this.fileProcessorWorker) {
         this.fileProcessorWorker = new Worker(new URL("../workers/fileProcessorWorker.js", import.meta.url), { type: "module" })
      }

      this.requestMoreFilesFromWorker = () => {
         if (this.workerDone) return
         this.fileProcessorWorker.postMessage({ type: "produce" })
      }

      this.uploadRuntime.setPendingWorkerFilesLength(this.uploadRuntime.pendingWorkerFilesLength + filesList.length)
      let totalBytes = 0
      for (const item of filesList) {
         if (typeOfUpload === uploadType.dragAndDropInput) {
            totalBytes += item.file.size
         } else {
            totalBytes += item.size
         }
      }
      this.uploadRuntime.setAllBytesToUpload(this.uploadRuntime.allBytesToUpload + totalBytes)

      this.fileProcessorWorker.onmessage = async event => {
         this.fileQueue.open()

         const { files, totalBytes, done } = event.data

         if (files && files.length > 0) {

            for (const file of files) {
               this.uploadRuntime.registerFile(file)
               this.uploadRuntime.setPendingWorkerFilesLength(this.uploadRuntime.pendingWorkerFilesLength - 1)
               await this.fileQueue.put(file)
            }
         }

         if (done) {
            console.log("closing file queue")
            this.fileQueue.close()
            this.uploadRuntime.workerDone = true
         }
      }

      // initialize worker state (one-time)
      this.fileProcessorWorker.postMessage({type: "init", typeOfUpload, folderContext, filesList, uploadId, encryptionMethod, parentPassword, lockFrom})

      // kickstart first batch
      this.requestMoreFilesFromWorker()
   }

   initRuntimeUpload() {
      if (this.uploadRuntime) return
      this.uploadRuntime = new UploadRuntime({ uploadFinishCallback: this.onUploadSessionFinished })
      this.uploadRuntime.onGlobalStateChange(snapshot => {
         this.uploadStore.onGlobalStateChange(snapshot)
      })
      this.uploadRuntime.onFileChange(
         ["status", "progress", "error", "fileObj", "frontendId"],
         ({ frontendId, field, current }) => {
            this.uploadStore.updateFileField(frontendId, field, current)
         }
      )
      this.uploadRuntime.onFileSaved((frontendId) => {
         this.uploadStore.onFileSaved(frontendId)
      })
      this.uploadRuntime.onUploadStateChange(
         (newState, prevState) => {
            if (newState === uploadState.noInternet) {
               this._startInternetProbe()
            } else if (prevState === uploadState.noInternet) {
               this._stopInternetProbe()
            }
         })
   }

   initQueues() {
      if (!this.fileQueue) {
         this.fileQueue = new AsyncQueue(5)
      } else {
         this.fileQueue.open()
      }
      if (!this.requestQueue) {
         this.requestQueue = new AsyncQueue(2)
      } else {
         this.requestQueue.open()
      }
      if (!this.discordResponseQueue) {
         this.discordResponseQueue = new AsyncQueue(5)
      } else {
         this.discordResponseQueue.open()
      }
      if (!this.backendFileQueue) {
         this.backendFileQueue = new AsyncQueue(5)
      } else {
         this.backendFileQueue.open()
      }
      if (!this.discordAttachmentQueue) {
         this.discordAttachmentQueue = new AsyncQueue(5)
      } else {
         this.discordAttachmentQueue.open()
      }
   }

   startProducer() {
      if (!this.requestProducer) {
         console.info("Recreating requestProducer")
         this.requestProducer = new RequestProducer({
            uploadRuntime: this.uploadRuntime,
            fileQueue: this.fileQueue,
            requestQueue: this.requestQueue,
            requestMoreFiles: this.requestMoreFiles.bind(this)
         })
      }
      if (!this.requestProducer.isRunning()) {
         console.info("Starting requestProducer")
         // fire-and-forget long-running task
         this.requestProducer.run()
            .catch(err => {
               console.error("RequestProducer crashed", err)
               this.uploadStore.state = uploadState.error
            })
      }
   }

   startConsumers() {
      /** ======= UPLOAD CONSUMERS =======*/
      if (!this.uploadConsumers.length) {
         console.info("Starting uploadConsumers!")
         this.uploadConsumers = []
         this.setUploadConcurrency(this.mainStore.settings.concurrentUploadRequests)
      }

      /** ======= DISCORD RESPONSE CONSUMER =======*/
      if (!this.discordResponseConsumer) {
         console.info("Recreating discordResponseConsumer!")
         this.discordResponseConsumer = new DiscordResponseConsumer({
            discordResponseQueue: this.discordResponseQueue,
            backendFileQueue: this.backendFileQueue,
            discordAttachmentQueue: this.discordAttachmentQueue,
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

      /** ======= BACKEND FILE CONSUMER =======*/
      if (!this.backendFileConsumer) {
         console.info("Recreating backendFileConsumer!")
         this.backendFileConsumer = new BackendFileConsumer({
            backendFileQueue: this.backendFileQueue,
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


      /** ======= DISCORD ATTACHMENT CONSUMER =======*/
      if (!this.discordAttachmentConsumer) {
         console.info("Recreating discordAttachmentConsumer!")
         this.discordAttachmentConsumer = new DiscordAttachmentConsumer({
            discordAttachmentQueue: this.discordAttachmentQueue,
            uploadRuntime: this.uploadRuntime
         })
      }
      if (!this.discordAttachmentConsumer.isRunning()) {
         console.info("Starting discordAttachmentConsumer!")
         this.discordAttachmentConsumer.run().catch(err => {
            console.error("DiscordAttachmentConsumer crashed", err)
            this.uploadStore.state = uploadState.error
         })
      }
   }

   setUploadConcurrency(target) {
      const current = this.uploadConsumers.length
      if (target === current) return

      if (target > current) {
         this._addConsumers(target - current)
      } else {
         this._removeConsumers(current - target)
      }
   }

   ensureQueuesOpen() {
      this.fileQueue?.open()
      this.requestQueue?.open()
      this.discordResponseQueue?.open()
      this.backendFileQueue?.open()
      this.discordAttachmentQueue?.open()
   }


   requestMoreFiles() {
      this.fileProcessorWorker.postMessage({ type: "produce" })
   }

   pauseAll() {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return
      this.uploadRuntime.setUploadingState(uploadState.paused)
      this.uploadConsumers.forEach(c => c.abortAll())
   }

   resumeAll() {
      if (this.uploadRuntime.uploadState !== uploadState.paused) return
      this.uploadRuntime.setUploadingState(uploadState.uploading)
      this.saveFilesIfNeeded()
   }

   saveFilesIfNeeded() {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return
      this.backendFileConsumer.saveFilesIfNeeded()

   }

   retrySaveFailedFiles() {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return
      getUploader().backendFileConsumer.retryFailedFiles()
   }

   retryGoneFile(frontendId) {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return
      this.ensureQueuesOpen()
      this.uploadConsumers.forEach(c => c.retryGoneFile(frontendId))
      let file = this.requestProducer.getGoneFile(frontendId)
      if (!file) return
      this.fileQueue.put(file).then(() => {
         this.startConsumers()
         this.startProducer()
         this.fileQueue.close()
      })
   }

   dismissFile(frontendId) {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return
      //todo well this leaves so much orphanded data
      this.uploadRuntime.deleteFileState(frontendId)
   }
   retryFailedRequests() {
      if (this.uploadRuntime.uploadState !== uploadState.uploading) return
      this.uploadConsumers.forEach(c => c.retryFailedRequests())
   }

   onUploadSessionFinished = () => {
      this.cleanup()
      this.uploadStore.onUploadFinishUI()
      showToast("success", "toasts.uploadFinished")
   }

   cleanup() {
      window.removeEventListener("beforeunload", beforeUnload)
      // this.stopInternetProbe()
      // this.fileProcessorWorker = null
      // this.fileQueue?.close()
      // this.requestQueue?.close()
      //
      // this.uploadConsumers.forEach(c => c.stop())
      //
      // this.uploadConsumers = []
      // this.fileQueue = null
      // this.requestQueue = null
      // this.requestProducer = null
      // this.uploadRuntime = null
   }

   _addConsumers(count) {
      for (let i = 0; i < count; i++) {
         const consumer = new DiscordUploadConsumer({
            requestQueue: this.requestQueue,
            discordResponseQueue: this.discordResponseQueue,
            uploadRuntime: this.uploadRuntime
         })

         this.uploadConsumers.push(consumer)
         consumer.run().catch(err => {
            console.error("DiscordUploadConsumer crashed", err)
            this.uploadStore.state = uploadState.error
         })
      }
   }

   _removeConsumers(count) {
      for (let i = 0; i < count; i++) {
         const consumer = this.uploadConsumers.pop()
         if (!consumer) break
         consumer.stop()
      }
   }

   _startInternetProbe() {
      if (this._internetProbeInterval) return

      this._internetProbeInterval = setInterval(async () => {
         try {
            await this._checkInternet()
            this._onInternetRestored()
         } catch {
         }
      }, 10000)
   }

   _onInternetRestored() {
      this._stopInternetProbe()

      if (this.uploadRuntime.uploadState !== uploadState.noInternet) return
      this.uploadRuntime.setUploadingState(uploadState.uploading)
   }

   async _checkInternet() {
      await checkWifi()
   }

   _stopInternetProbe() {
      if (!this._internetProbeInterval) return
      clearInterval(this._internetProbeInterval)
      this._internetProbeInterval = null
   }

}

let _uploaderInstance = null


export function getUploader() {
   if (!_uploaderInstance) {
      _uploaderInstance = new Uploader()
   }
   return _uploaderInstance
}


const beforeUnload = event => {
   event.preventDefault()
   event.returnValue = ""
}
