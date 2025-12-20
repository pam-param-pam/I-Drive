import { defineStore } from "pinia"
import { attachmentType, fileUploadStatus, uploadState } from "@/utils/constants.js"
import { FileStateHolder } from "@/upload/FileStateHolder.js"
import { getUploader } from "@/upload/Uploader.js"
import { checkFilesSizes, isErrorStatus } from "@/upload/utils/uploadHelper.js"
import { useMainStore } from "@/stores/mainStore.js"
import { showToast } from "@/utils/common.js"

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
         return source.slice(0, 20)
      },

      filesInUploadCount() {
         return Object.keys(this.files).length + this.pendingWorkerFilesLength
      },
      progress() {
         return (this.allBytesUploaded / this.allBytesToUpload) * 100
      }

   },

   actions: {

      registerFile(snapshot) {
         this.files[snapshot.frontendId] = snapshot
      },

      updateFile(frontendId, snapshot) {
         if (!this.files[frontendId]) return
         this.files[frontendId] = snapshot
      },

      setPendingWorkerFilesLength(value) {
         this.pendingWorkerFilesLength = value
      },

      setAllBytesToUpload(value) {
         this.allBytesToUpload = value
      },

      setAllBytesUploaded(value) {
         this.allBytesUploaded = value
      },

      setUploadSpeed(value) {
         this.uploadSpeed = value
      },

      setState(state) {
         this.state = state
      },

      setEta(eta) {
         this.eta = eta
      },

      deleteFileState(frontendId) {
         delete this.files[frontendId]
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
      },





      /* todo

      retryFailSaveFile(frontendId) {
         getUploader().backendManager.reSaveFile(frontendId)
      },

      async retryUploadFile(frontendId) {
         await getUploader().discordUploader.reUploadRequest(frontendId)
         getUploader().processUploads()
      },

      retryGoneFile(frontendId) {
         let state = this.getFileState(frontendId)
         if (!state) return
         this.setStatus(frontendId, fileUploadStatus.retrying)
         let newFile = { systemFile: state.systemFile, fileObj: state.fileObj }
         this.queue.unshift(newFile)
         getUploader().processUploads()
      },

      dismissFile(frontendId) {
         let index = this.fileState.findIndex(file => file.frontendId === frontendId)
         if (index !== -1) {
            this.fileState.splice(index, 1)
         } else {
            console.warn("Failed to find file: " + frontendId + " in fileState")
         }
         this.onUploadFinish()
      },
      */


   }
})


