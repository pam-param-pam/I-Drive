import { attachmentType } from "@/utils/constants.js"

export class DiscordAttachmentConsumer {
   constructor({ discordAttachmentQueue, uploadRuntime }) {
      this.queue = discordAttachmentQueue
      this.uploadRuntime = uploadRuntime
      this.running = false

      this.BATCH_SIZE = 42

      // attachments waiting until file is saved
      this.pending = {
         file: new Map(),
         thumbnail: new Map(),
      }

      // attachments eligible for batching
      this.ready = {
         file: [],
         thumbnail: [],
      }

      this.uploadRuntime.onFileSaved((frontendId) => {
         this._onFileSaved(frontendId)
      })
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
         const { attachment, discordAttachment } = await this.queue.take()
         if (!attachment) break

         await this.processAttachment(attachment, discordAttachment)
      }

      this.running = false
   }

   async processAttachment(attachment, discordAttachment) {
      const frontendId = attachment.fileObj.frontendId

      const entry = {
         attachment_id: discordAttachment.id,
         url: discordAttachment.url,
         frontendId,
      }

      if (attachment.type === attachmentType.file) {
         this._addPending("file", frontendId, entry)
      } else if (attachment.type === attachmentType.thumbnail) {
         this._addPending("thumbnail", frontendId, entry)
      }
   }

   _addPending(kind, frontendId, entry) {
      let list = this.pending[kind].get(frontendId)
      if (!list) {
         list = []
         this.pending[kind].set(frontendId, list)
      }
      list.push(entry)
   }

   _onFileSaved(frontendId) {
      console.log("_onFileSaved!!!!")
      this._flushPendingForFile("file", frontendId)
      this._flushPendingForFile("thumbnail", frontendId)

      this._maybeEmitBatches("file")
      this._maybeEmitBatches("thumbnail")
   }

   _flushPendingForFile(kind, frontendId) {
      const list = this.pending[kind].get(frontendId)
      if (!list || list.length === 0) return

      this.pending[kind].delete(frontendId)
      this.ready[kind].push(...list)
   }

   _maybeEmitBatches(kind) {
      while (this.ready[kind].length >= this.BATCH_SIZE) {
         const batch = this.ready[kind].splice(0, this.BATCH_SIZE)
         this._emitBatch(kind, batch)
      }

      // flush remaining when upload is done
      if (this.uploadRuntime.fileStates.size === 0 && this.ready[kind].length > 0) { //todo change this
         const batch = this.ready[kind].splice(0, this.ready[kind].length)
         this._emitBatch(kind, batch)
      }
   }

   _emitBatch(kind, batch) {
      console.log("_emitBatch")
      console.log(`[DiscordAttachmentConsumer] ready ${kind} batch (${batch.length})`, batch.map(b => b.attachment_id))

      // hook point:
      // this.uploadRuntime.submitBatch(kind, batch)
      // or: this.someQueue.put({ kind, batch })
   }
}
