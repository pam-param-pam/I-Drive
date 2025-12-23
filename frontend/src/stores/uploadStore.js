import { defineStore } from "pinia"
import { fileUploadStatus, uploadState } from "@/utils/constants.js"

export const useUploadStore = defineStore("upload", {
   state: () => ({
      state: uploadState.idle,

      files: {},
      //UI
      eta: Infinity,
      allBytesToUpload: 0,
      allBytesUploaded: 0,
      uploadSpeed: 0,
      pendingWorkerFilesLength: 0
   }),

   getters: {

      isAllFinished() {
        return false
      },

      filesInUpload() {
         const all = Object.values(this.files)

         const uploading = all.filter(f => f.status === fileUploadStatus.uploading)

         const source = uploading.length > 0 ? uploading : all

         return source
            .slice()
            .sort((a, b) =>
               (b.lastModifiedTimestamp || 0) - (a.lastModifiedTimestamp || 0)
            )
            .slice(0, 20)
      },

      filesInUploadCount() {
         return Object.keys(this.files).length + this.pendingWorkerFilesLength
      },
      progress() {
         return (this.allBytesUploaded / this.allBytesToUpload) * 100
      }

   },

   actions: {
      onFileSaved(frontendId) {
         delete this.files[frontendId]
      },

      updateFileField(frontendId, field, value) {
         let file = this.files[frontendId]
         if (!file) {
            file = this.files[frontendId] = {}
         }

         if (file[field] === value) return

         file[field] = value
         file.lastModifiedTimestamp = Date.now()
      },

      onGlobalStateChange(snapshot) {
         this.allBytesUploaded = snapshot.allBytesUploaded
         this.allBytesToUpload = snapshot.allBytesToUpload
         this.state = snapshot.uploadState
         this.pendingWorkerFilesLength = snapshot.pendingWorkerFilesLength
         this.uploadSpeed = snapshot.speed
         this.eta = snapshot.eta
      },

      onUploadFinishUI() {
         this.state = uploadState.idle
         this.files = {}
         this.eta = Infinity
         this.allBytesToUpload = 0
         this.allBytesUploaded = 0
         this.uploadSpeed = 0
      },

      addToWebhooks(webhook) {
         this.webhooks.push(webhook)
      },
      removeWebhook(discord_id) {
         this.webhooks = this.webhooks.filter(webhook => webhook.discord_id !== discord_id)
      },
      setWebhooks(value) {
         this.webhooks = value
      },
      setAttachmentName(value) {
         this.attachmentName = value
      },
      setFileExtensions(value) {
         this.fileExtensions = value
      }
   }
})


