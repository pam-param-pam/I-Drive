import { AsyncQueue } from "@/transfers/upload/AsyncQueue.js"

export class UploadQueues {
   constructor() {
      this.fileQueue = new AsyncQueue(5)
      this.requestQueue = new AsyncQueue(2)
      this.discordResponseQueue = new AsyncQueue(5)
      this.backendFileQueue = new AsyncQueue(5)
   }

   openAll() {
      this.fileQueue.open()
      this.requestQueue.open()
      this.discordResponseQueue.open()
      this.backendFileQueue.open()
   }

   closeAll() {
      this.fileQueue.close()
      this.requestQueue.close()
      this.discordResponseQueue.close()
      this.backendFileQueue.close()
   }

   logStats() {
      console.log(
         "fileQueue:", this.fileQueue.size(), "closed:", this.fileQueue.closed,
         "requestQueue:", this.requestQueue.size(), "closed:", this.requestQueue.closed,
         "discordResponseQueue:", this.discordResponseQueue.size(), "closed:", this.discordResponseQueue.closed,
         "backendFileQueue:", this.backendFileQueue.size(), "closed:", this.backendFileQueue.closed
      )
   }
}