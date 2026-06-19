// downloader.js
import { reactive, readonly } from "vue"

class Downloader {
   static instance = null

   // Private fields
   #queue = []
   #activeDownloads = new Map()
   #isProcessing = false
   #isPaused = false
   #abortController = null
   #maxConcurrent = 3
   #store = null

   constructor() {
      if (Downloader.instance) {
         return Downloader.instance
      }

      // Initialize reactive store
      this.#store = reactive({
         queue: [],
         activeDownloads: {},
         completed: [],
         failed: [],
         totalProgress: 0,
         isProcessing: false,
         isPaused: false,
         stats: {
            total: 0,
            completed: 0,
            failed: 0,
            active: 0,
            paused: 0
         }
      })

      Downloader.instance = this
   }

   static getInstance() {
      if (!Downloader.instance) {
         Downloader.instance = new Downloader()
      }
      return Downloader.instance
   }

   // Get readonly store for Vue components
   getStore() {
      return readonly(this.#store)
   }

   // Add file to download queue
   addToQueue(fileConfig) {
      const downloadItem = {
         id: this.#generateId(),
         url: fileConfig.url,
         filename: fileConfig.filename || this.#getFilenameFromUrl(fileConfig.url),
         status: "pending",
         progress: 0,
         totalBytes: 0,
         downloadedBytes: 0,
         speed: 0,
         error: null,
         startTime: null,
         endTime: null,
         controller: null,
         ...fileConfig
      }

      this.#queue.push(downloadItem)
      this.#updateStore()

      // Start processing if not already
      if (!this.#isProcessing && !this.#isPaused) {
         this.#processQueue()
      }

      return downloadItem.id
   }

   // Pause a specific download
   pauseDownload(id) {
      const item = this.#findItem(id)
      if (!item || item.status !== "downloading") return false

      item.status = "paused"
      if (item.controller) {
         item.controller.abort()
         item.controller = null
      }

      this.#activeDownloads.delete(id)
      this.#updateStore()
      return true
   }

   // Resume a specific download
   async resumeDownload(id) {
      const item = this.#findItem(id)
      if (!item || item.status !== "paused") return false

      item.status = "pending"
      this.#updateStore()

      if (!this.#isPaused) {
         await this.#processQueue()
      }
      return true
   }

   // Cancel a specific download
   cancelDownload(id) {
      const item = this.#findItem(id)
      if (!item) return false

      if (item.controller) {
         item.controller.abort()
         item.controller = null
      }

      item.status = "canceled"
      this.#activeDownloads.delete(id)
      this.#updateStore()

      // Remove from queue
      this.#queue = this.#queue.filter(item => item.id !== id)
      this.#updateStore()

      return true
   }

   // Pause all downloads
   pauseAll() {
      if (this.#isPaused) return

      this.#isPaused = true
      this.#abortController?.abort()

      // Pause all active downloads
      for (const [id, item] of this.#activeDownloads) {
         if (item.controller) {
            item.controller.abort()
            item.controller = null
         }
         item.status = "paused"
      }

      this.#activeDownloads.clear()
      this.#updateStore()
   }

   // Resume all downloads
   async resumeAll() {
      if (!this.#isPaused) return

      this.#isPaused = false
      this.#updateStore()

      // Reset paused items to pending
      for (const item of this.#queue) {
         if (item.status === "paused") {
            item.status = "pending"
         }
      }

      await this.#processQueue()
   }

   // Abort/Cancel all downloads
   abortAll() {
      this.#isPaused = false
      this.#abortController?.abort()

      // Cancel all active downloads
      for (const [id, item] of this.#activeDownloads) {
         if (item.controller) {
            item.controller.abort()
            item.controller = null
         }
         item.status = "canceled"
      }

      this.#activeDownloads.clear()
      this.#queue = []
      this.#updateStore()
   }

   // Private methods
   async #processQueue() {
      if (this.#isProcessing || this.#isPaused) return

      this.#isProcessing = true
      this.#updateStore()

      while (this.#queue.length > 0 && this.#activeDownloads.size < this.#maxConcurrent) {
         // Find next pending item
         const index = this.#queue.findIndex(item => item.status === "pending")
         if (index === -1) break

         const item = this.#queue[index]
         item.status = "downloading"
         item.startTime = Date.now()

         // Create abort controller for this download
         item.controller = new AbortController()

         // Start download
         this.#activeDownloads.set(item.id, item)
         this.#updateStore()

         this.#downloadFile(item).catch(error => {
            if (error.name !== "AbortError") {
               item.status = "failed"
               item.error = error.message
               this.#activeDownloads.delete(item.id)
               this.#updateStore()
            }
         })
      }

      this.#isProcessing = false
      this.#updateStore()
   }

   async #downloadFile(item) {
      try {
         const response = await fetch(item.url, {
            signal: item.controller.signal,
            headers: {
               "Range": `bytes=${item.downloadedBytes}-`
            }
         })

         if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)

         const contentLength = parseInt(response.headers.get("content-length") || "0")
         const totalBytes = item.totalBytes || contentLength + item.downloadedBytes
         item.totalBytes = totalBytes

         const reader = response.body.getReader()
         const contentLengthBytes = item.totalBytes

         let startTime = Date.now()
         let bytesDownloaded = item.downloadedBytes
         let lastProgressUpdate = Date.now()

         while (true) {
            const { done, value } = await reader.read()

            if (done) {
               // Download complete
               item.status = "completed"
               item.progress = 100
               item.downloadedBytes = item.totalBytes
               item.endTime = Date.now()
               item.controller = null
               this.#activeDownloads.delete(item.id)

               // Move to completed
               const queueIndex = this.#queue.indexOf(item)
               if (queueIndex !== -1) {
                  this.#queue.splice(queueIndex, 1)
               }

               this.#updateStore()
               break
            }

            // Update progress
            bytesDownloaded += value.length
            item.downloadedBytes = bytesDownloaded
            item.progress = Math.min((bytesDownloaded / contentLengthBytes) * 100, 100)

            // Calculate speed
            const now = Date.now()
            if (now - lastProgressUpdate > 1000) {
               const timeDelta = (now - startTime) / 1000
               item.speed = bytesDownloaded / timeDelta
               lastProgressUpdate = now
            }

            this.#updateStore()
         }
      } catch (error) {
         if (error.name === "AbortError") {
            // Download was paused or canceled
            if (item.status !== "canceled") {
               item.status = "paused"
               item.controller = null
               this.#activeDownloads.delete(item.id)
            }
            throw error
         }

         item.status = "failed"
         item.error = error.message
         item.controller = null
         this.#activeDownloads.delete(item.id)
         this.#updateStore()
         throw error
      }
   }

   #updateStore() {
      const activeDownloads = {}
      for (const [id, item] of this.#activeDownloads) {
         activeDownloads[id] = {
            id: item.id,
            filename: item.filename,
            progress: item.progress,
            downloadedBytes: item.downloadedBytes,
            totalBytes: item.totalBytes,
            speed: item.speed,
            status: item.status
         }
      }

      this.#store.queue = this.#queue.map(item => ({
         id: item.id,
         filename: item.filename,
         status: item.status,
         progress: item.progress,
         error: item.error
      }))

      this.#store.activeDownloads = activeDownloads
      this.#store.isProcessing = this.#isProcessing
      this.#store.isPaused = this.#isPaused

      // Calculate stats
      const stats = {
         total: this.#queue.length + this.#activeDownloads.size,
         completed: this.#queue.filter(item => item.status === "completed").length,
         failed: this.#queue.filter(item => item.status === "failed").length,
         active: this.#activeDownloads.size,
         paused: this.#queue.filter(item => item.status === "paused").length
      }
      this.#store.stats = stats

      // Calculate total progress
      const allItems = [...this.#queue, ...Array.from(this.#activeDownloads.values())]
      if (allItems.length > 0) {
         const totalProgress = allItems.reduce((sum, item) => sum + (item.progress || 0), 0)
         this.#store.totalProgress = totalProgress / allItems.length
      } else {
         this.#store.totalProgress = 0
      }
   }

   #findItem(id) {
      return this.#queue.find(item => item.id === id) ||
         this.#activeDownloads.get(id)
   }

   #generateId() {
      return Date.now().toString(36) + Math.random().toString(36).substr(2, 9)
   }

   #getFilenameFromUrl(url) {
      try {
         return url.split("/").pop() || "download"
      } catch {
         return "download"
      }
   }

   // Set maximum concurrent downloads
   setMaxConcurrent(count) {
      if (count > 0) {
         this.#maxConcurrent = count
      }
   }
}


// Vue composable for easy integration
export function useDownloader() {
   const downloader = Downloader.getInstance()
   const store = downloader.getStore()

   return {
      // State
      queue: store.queue,
      activeDownloads: store.activeDownloads,
      stats: store.stats,
      totalProgress: store.totalProgress,
      isProcessing: store.isProcessing,
      isPaused: store.isPaused,

      // Actions
      addToQueue: (fileConfig) => downloader.addToQueue(fileConfig),
      pauseDownload: (id) => downloader.pauseDownload(id),
      resumeDownload: (id) => downloader.resumeDownload(id),
      cancelDownload: (id) => downloader.cancelDownload(id),
      pauseAll: () => downloader.pauseAll(),
      resumeAll: () => downloader.resumeAll(),
      abortAll: () => downloader.abortAll(),
      setMaxConcurrent: (count) => downloader.setMaxConcurrent(count)
   }
}


export default Downloader