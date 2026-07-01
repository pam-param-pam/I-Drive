import { defineStore } from "pinia"
import { uploadFileStatus, uploadState } from "@/transfers/upload/constants.js"
import { downloadFileStatus, downloadState } from "@/transfers/downloads/constants.js"

export const useTransferStore = defineStore("transfer", {
   state: () => ({
      upload: {
         state: uploadState.idle,
         files: {},
         eta: Infinity,
         allBytesToUpload: 0,
         allBytesUploaded: 0,
         uploadSpeed: 0,
         pendingWorkerFilesLength: 0,
         webhooks: [],
         attachmentName: null,
         fileExtensions: []
      },

      download: {
         state: downloadState.idle,
         files: {},
         eta: Infinity,
         allBytesToDownload: 0,
         allBytesDownloaded: 0,
         pendingQueueFiles: 0,
         downloadSpeed: 0,
      }
   }),

   getters: {
      filesInUpload() {
         const all = Object.values(this.upload.files)
         const uploading = all.filter(f => f.status === uploadFileStatus.uploading)
         const source = uploading.length > 0 ? uploading : all

         return source
            .slice()
            .sort((a, b) => (b.lastModifiedTimestamp || 0) - (a.lastModifiedTimestamp || 0))
            .slice(0, 20)
      },

      filesInUploadCount() {
         return Object.keys(this.upload.files).length + this.upload.pendingWorkerFilesLength
      },

      uploadProgress() {
         return (this.upload.allBytesUploaded / this.upload.allBytesToUpload) * 100
      },

      filesInDownload() {
         const all = Object.values(this.download.files)
         const downloading = all.filter(f => f.status === downloadFileStatus.downloading)
         const source = downloading.length > 0 ? downloading : all

         return source
            .slice()
            .sort((a, b) => (b.lastModifiedTimestamp || 0) - (a.lastModifiedTimestamp || 0))
            .slice(0, 20)
      },

      filesInDownloadCount() {
         return Object.keys(this.download.files).length + this.download.pendingQueueFiles
      },

      downloadProgress() {
         return (this.download.allBytesDownloaded / this.download.allBytesToDownload) * 100
      },
      totalProgress() {
         const parts = []

         if (Number.isFinite(this.downloadProgress)) {
            parts.push(this.downloadProgress)
         }

         if (Number.isFinite(this.uploadProgress)) {
            parts.push(this.uploadProgress)
         }

         if (!parts.length) return null

         return Math.floor(parts.reduce((sum, progress) => sum + progress, 0) / parts.length)
      }
   },

   actions: {
      onUploadFileSaved(frontendId) {
         delete this.upload.files[frontendId]
      },

      updateUploadFileField(frontendId, field, value) {
         let file = this.upload.files[frontendId]
         if (!file) {
            file = this.upload.files[frontendId] = {}
         }
         if (file[field] === value) return

         file[field] = value
         file.lastModifiedTimestamp = Date.now()
      },

      onUploadGlobalStateChange(snapshot) {
         this.upload.allBytesUploaded = snapshot.allBytesUploaded
         this.upload.allBytesToUpload = snapshot.allBytesToUpload
         this.upload.state = snapshot.uploadState
         this.upload.pendingWorkerFilesLength = snapshot.pendingWorkerFilesLength
         this.upload.uploadSpeed = snapshot.speed
         this.upload.eta = snapshot.eta
      },

      cleanupUpload() {
         this.upload.state = uploadState.idle

         for (const key of Object.keys(this.upload.files)) {
            delete this.upload.files[key]
         }

         this.upload.eta = Infinity
         this.upload.allBytesToUpload = 0
         this.upload.allBytesUploaded = 0
         this.upload.uploadSpeed = 0
         this.upload.pendingWorkerFilesLength = 0
      },

      addToWebhooks(webhook) {
         this.upload.webhooks.push(webhook)
      },

      removeWebhook(discord_id) {
         this.upload.webhooks = this.upload.webhooks.filter(webhook => webhook.discord_id !== discord_id)
      },

      setWebhooks(value) {
         this.upload.webhooks = value
      },

      setAttachmentName(value) {
         this.upload.attachmentName = value
      },

      setFileExtensions(value) {
         this.upload.fileExtensions = value
      },

      onDownloadFileSaved(frontendId) {
         delete this.download.files[frontendId]
      },

      updateDownloadFileField(frontendId, field, value) {
         let file = this.download.files[frontendId]
         if (!file) {
            file = this.download.files[frontendId] = {}
         }
         if (file[field] === value) return

         file[field] = value
         file.lastModifiedTimestamp = Date.now()
      },

      onDownloadGlobalStateChange(snapshot) {
         this.download.allBytesDownloaded = snapshot.allBytesDownloaded
         this.download.allBytesToDownload = snapshot.allBytesToDownload
         this.download.state = snapshot.downloadState
         this.download.downloadSpeed = snapshot.speed
         this.download.pendingQueueFiles = snapshot.pendingQueueFiles
         this.download.eta = snapshot.eta
      },

      cleanupDownload() {
         this.download.state = downloadState.idle

         for (const key of Object.keys(this.download.files)) {
            delete this.download.files[key]
         }

         this.download.eta = Infinity
         this.download.allBytesToDownload = 0
         this.download.allBytesDownloaded = 0
         this.download.downloadSpeed = 0
      },

      cleanup() {
         this.cleanupUpload()
         this.cleanupDownload()
      }
   }
})