import { DiscordUploadStage } from "@/transfers/upload/workers/DiscordUploadStage.js"
import { workerExitReason } from "@/transfers/shared/constants.js"
import { uploadFileStatus, uploadState } from "@/transfers/upload/constants.js"

export class DiscordUploadPool {
   constructor({ requestQueue, discordResponseQueue, uploadRuntime }) {
      this.requestQueue = requestQueue
      this.discordResponseQueue = discordResponseQueue
      this.uploadRuntime = uploadRuntime

      this.consumers = []
      this.activeCount = 0
      this.inputEnded = false
      this.outputClosed = false

      this.failedRequests = []
      this._retryPromise = null
   }

   setConcurrency(target) {
      const current = this.consumers.length
      if (target === current) return

      if (target > current) {
         this.addConsumers(target - current)
      } else {
         this.removeConsumers(current - target)
      }
   }

   addConsumers(count) {
      for (let i = 0; i < count; i++) {
         this.startOneConsumer()
      }
   }

   startOneConsumer() {
      const consumer = new DiscordUploadStage({
         requestQueue: this.requestQueue,
         discordResponseQueue: this.discordResponseQueue,
         uploadRuntime: this.uploadRuntime,
         onFailedRequest: request => this.failedRequests.push(request)
      })

      this.consumers.push(consumer)
      this.activeCount++

      consumer.run()
         .then(exitReason => {
            if (exitReason === workerExitReason.inputEnded) {
               this.inputEnded = true
            }
         })
         .catch(err => {
            console.error("DiscordUploadConsumer crashed", err)
            this.uploadRuntime.setUploadingState(uploadState.error)
         })
         .finally(() => {
            this.activeCount--
            this.consumers = this.consumers.filter(c => c !== consumer)
            this.closeOutputIfFinished()
         })
   }

   removeConsumers(count) {
      for (let i = 0; i < count; i++) {
         const consumer = this.consumers.pop()
         if (!consumer) break

         consumer.stop()
      }
   }

   async retryGoneFile(frontendId) {
      await this.retryFailedUploads(frontendId)
   }

   async retryFailedUploads(frontendId = null) {
      while (this._retryPromise) {
         await this._retryPromise
      }

      const requests = this.takeFailedRequests(frontendId)
      if (!requests.length) return

      const retryPromise = this.requeueRequests(requests)
      this._retryPromise = retryPromise

      try {
         await retryPromise
      } finally {
         if (this._retryPromise === retryPromise) {
            this._retryPromise = null
         }
      }
   }

   takeFailedRequests(frontendId = null) {
      if (!frontendId) {
         const requests = this.failedRequests
         this.failedRequests = []
         return requests
      }

      const requestsToRetry = []

      this.failedRequests = this.failedRequests.filter(request => {
         const containsFile = request.attachments.some(att => att.fileObj.frontendId === frontendId)

         if (containsFile) {
            requestsToRetry.push(request)
            return false
         }

         return true
      })

      return requestsToRetry
   }

   async requeueRequests(requests) {
      for (const request of requests) {
         for (const attachment of request.attachments) {
            const fileState = this.uploadRuntime.getFileState(attachment.fileObj.frontendId)
            fileState.setStatus(uploadFileStatus.retrying)
            fileState.setError(null)
         }

         await this.requestQueue.put(request)
      }
   }

   abortAllUploadRequests() {
      this.consumers.forEach(c => c.abortAllUploadRequests())
   }

   closeOutputIfFinished() {
      if (this.outputClosed) return
      if (!this.inputEnded) return
      if (this.activeCount > 0) return

      this.discordResponseQueue.close()
      this.outputClosed = true
   }

   async stopAll() {
      const consumers = [...this.consumers]
      this.consumers = []

      await Promise.all(consumers.map(c => c.stop()))
   }

   async killAll() {
      const consumers = [...this.consumers]
      this.consumers = []

      await Promise.all(consumers.map(c => c.kill()))
   }
}