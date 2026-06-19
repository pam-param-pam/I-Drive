import { defineStore } from "pinia"
import { downloadFileStatus, downloadState } from "@/utils/constants.js"



export const useDownloadStore = defineStore("download", {
   state: () => ({
      filesInDownload: [],
      processStatus: downloadState.idle,
      downloadSpeed: 0,
      downloadEta: Infinity,
      listenerAttached: false
   }),

   getters: {
      filesInDownloadCount(state) {
         return state.filesInDownload.length
      },

      activeDownloads(state) {
         return state.filesInDownload.filter(fileState => {
            return fileState.status === downloadFileStatus.downloading || fileState.status === downloadFileStatus.queued
         })
      },

      pausedDownloads(state) {
         return state.filesInDownload.filter(fileState => fileState.status === downloadFileStatus.paused)
      },

      hasDownloads(state) {
         return state.filesInDownload.length > 0
      },

      isPaused(state) {
         return state.processStatus === downloadFileStatus.paused
      },

      isDownloading(state) {
         return state.processStatus === downloadFileStatus.downloading
      }
   },

   actions: {
      attachServiceWorkerListener() {
         if (this.listenerAttached) return
         if (!("serviceWorker" in navigator)) return

         this.listenerAttached = true

         navigator.serviceWorker.addEventListener("message", event => {
            const message = event.data

            if (message?.type !== "DOWNLOAD_EVENT") {
               return
            }

            this.applyDownloadEvent(message)
         })
      },

      applyDownloadEvent(event) {
         let fileState = this.filesInDownload.find(fileState => fileState.fileObj.id === event.fileId)

         if (!fileState && event.status !== downloadFileStatus.completed && event.status !== downloadFileStatus.canceled) {
            fileState = this.createFileStateFromEvent(event)
            this.filesInDownload.push(fileState)
         }

         if (fileState) {
            this.patchFileStateFromEvent(fileState, event)
         }

         if (event.status === downloadFileStatus.completed || event.status === downloadFileStatus.canceled) {
            this.filesInDownload = this.filesInDownload.filter(fileState => fileState.fileObj.id !== event.fileId)
         }

         this.recalculateProcessStatus()
         this.recalculateSpeedAndEta()
      },

      createFileStateFromEvent(event) {
         return {
            fileObj: {
               id: event.fileId,
               frontendId: event.fileId,
               name: event.name,
               type: event.type,
               size: event.size,
               url: event.download_url
            },

            status: event.status || downloadFileStatus.queued,
            progress: event.progress || 0,
            error: event.error || null,

            transferredBytes: event.transferredBytes || 0,
            totalBytes: event.totalBytes || event.size || null,

            speed: event.speed || 0,
            eta: event.eta || Infinity,

            startedAt: event.startedAt || event.time || new Date().toISOString(),
            updatedAt: event.time || new Date().toISOString(),

            canPause: true,
            canResume: false,
            canCancel: true
         }
      },

      patchFileStateFromEvent(fileState, event) {
         fileState.status = this.normalizeStatus(event.status)
         fileState.updatedAt = event.time || new Date().toISOString()

         if (event.name || event.filename) {
            fileState.fileObj.name = event.name || event.filename
         }

         if (event.mimeType || event.type) {
            fileState.fileObj.type = event.mimeType || event.type
         }

         if (event.totalBytes !== undefined && event.totalBytes !== null) {
            fileState.totalBytes = event.totalBytes
            fileState.fileObj.size = event.totalBytes
         }

         if (event.transferredBytes !== undefined && event.transferredBytes !== null) {
            fileState.transferredBytes = event.transferredBytes
         }

         if (event.progress !== undefined && event.progress !== null) {
            fileState.progress = event.progress
         } else if (fileState.totalBytes > 0) {
            fileState.progress = Math.floor((fileState.transferredBytes / fileState.totalBytes) * 100)
         }

         if (event.speed !== undefined && event.speed !== null) {
            fileState.speed = event.speed
         }

         if (event.eta !== undefined && event.eta !== null) {
            fileState.eta = event.eta
         }

         fileState.error = event.error || null

         fileState.canPause = fileState.status === downloadFileStatus.downloading || fileState.status === downloadFileStatus.queued
         fileState.canResume = fileState.status === downloadFileStatus.paused
         fileState.canCancel = fileState.status !== downloadFileStatus.completed && fileState.status !== downloadFileStatus.canceled
      },

      normalizeStatus(status) {
         if (status === "running") return downloadFileStatus.downloading
         if (status === "progress") return downloadFileStatus.downloading
         return status
      },

      recalculateProcessStatus() {
         if (this.filesInDownload.length === 0) {
            this.processStatus = downloadFileStatus.idle
            return
         }

         if (this.filesInDownload.some(fileState => fileState.status === downloadFileStatus.noInternet)) {
            this.processStatus = downloadFileStatus.noInternet
            return
         }

         if (this.filesInDownload.some(fileState => fileState.status === downloadFileStatus.error)) {
            this.processStatus = downloadFileStatus.error
            return
         }

         if (this.filesInDownload.some(fileState => fileState.status === downloadFileStatus.downloading || fileState.status === downloadFileStatus.queued)) {
            this.processStatus = downloadFileStatus.downloading
            return
         }

         if (this.filesInDownload.every(fileState => fileState.status === downloadFileStatus.paused)) {
            this.processStatus = downloadFileStatus.paused
            return
         }

         this.processStatus = downloadFileStatus.idle
      },

      recalculateSpeedAndEta() {
         if (this.filesInDownload.length === 0) {
            this.downloadSpeed = 0
            this.downloadEta = Infinity
            return
         }

         this.downloadSpeed = this.filesInDownload.reduce((sum, fileState) => sum + (fileState.speed || 0), 0)

         const remainingBytes = this.filesInDownload.reduce((sum, fileState) => {
            if (!fileState.totalBytes) return sum
            return sum + Math.max(0, fileState.totalBytes - fileState.transferredBytes)
         }, 0)

         if (this.downloadSpeed > 0 && remainingBytes > 0) {
            this.downloadEta = remainingBytes / this.downloadSpeed
         } else {
            this.downloadEta = Infinity
         }
      },

      pauseFile(fileId) {
         this.postToServiceWorker({
            type: "DOWNLOAD_PAUSE",
            fileId
         })
      },

      resumeFile(fileId) {
         this.postToServiceWorker({
            type: "DOWNLOAD_RESUME",
            fileId
         })
      },

      cancelFile(fileId) {
         this.postToServiceWorker({
            type: "DOWNLOAD_CANCEL",
            fileId
         })
      },

      pauseAll() {
         this.postToServiceWorker({
            type: "DOWNLOAD_PAUSE_ALL"
         })
      },

      resumeAll() {
         this.postToServiceWorker({
            type: "DOWNLOAD_RESUME_ALL"
         })
      },

      abortAll() {
         this.postToServiceWorker({
            type: "DOWNLOAD_ABORT_ALL"
         })
      },

      postToServiceWorker(message) {
         const controller = navigator.serviceWorker?.controller

         if (!controller) {
            console.warn("No active service worker controller")
            return
         }

         controller.postMessage(message)
      },

      clearCompletedAndCanceled() {
         this.filesInDownload = this.filesInDownload.filter(fileState => {
            return fileState.status !== downloadFileStatus.completed && fileState.status !== downloadFileStatus.canceled
         })

         this.recalculateProcessStatus()
         this.recalculateSpeedAndEta()
      }
   }
})