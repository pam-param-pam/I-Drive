export class DiscordAttachmentConsumer {
   constructor({ discordAttachmentQueue, uploadRuntime }) {
      this.queue = discordAttachmentQueue
      this.uploadRuntime = uploadRuntime
      this.running = true
   }

   stop() {
      this.running = false
   }
   isRunning() {
      return this.running
   }
   async run() {
      if (this.running) {
         console.warn("DiscordAttachmentConsumer is already running!")
         return
      }
      this.running = true
      while (this.running) {
         const { frontendId, attachment } = await this.queue.take()
         if (!attachment) break

         try {
            await this.processAttachment(frontendId, attachment)
         } catch (err) {
            console.error("DiscordAttachmentProcessor error", err)
         }
      }
      this.running = false
   }

   async processAttachment(frontendId, attachment) {
      // console.log(frontendId)
      // console.log(attachment)
   }

}
