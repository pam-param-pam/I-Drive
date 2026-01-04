import { attachmentType } from "@/utils/constants.js"

export class DiscordResponseConsumer {
   constructor({ discordResponseQueue, backendFileQueue, discordAttachmentQueue, uploadRuntime }) {
      this.discordResponseQueue = discordResponseQueue
      this.backendFileQueue = backendFileQueue
      this.discordAttachmentQueue = discordAttachmentQueue
      this.uploadRuntime = uploadRuntime
      this.running = false
      this.backendState = new Map()

      this.uploadRuntime.onFileChange(["videoMetadata", "rawMetadata"], ({ frontendId, field, current }) => {
            this.onFileMetadata(frontendId, field, current)
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
         console.warn("DiscordResponseConsumer is already running!")
         return
      }
      this.running = true
      while (this.running) {
         const result = await this.discordResponseQueue.take()
         if (!result) {
            console.warn("DiscordResponseConsumer breaking!")
            break
         }
         await this.handleDiscordResult(result)
      }
      this.running = false
   }

   async handleDiscordResult({ request, discordResponse }) {
      for (let i = 0; i < request.attachments.length; i++) {
         const attachment = request.attachments[i]
         const discordAttachment = discordResponse.data.attachments[i]
         await this.discordAttachmentQueue.put({"discordAttachment": discordAttachment, "attachment": attachment})
         this.fillAttachmentInfo(attachment, discordResponse, discordAttachment)
      }
   }

   getOrCreateState(fileObj) {
      const fileState = this.uploadRuntime.getFileState(fileObj.frontendId)

      if (!this.backendState.has(fileObj.frontendId)) {
         this.backendState.set(fileObj.frontendId, {
            name: fileObj.name,
            parent_id: fileObj.folderId,
            size: fileObj.size,
            frontend_id: fileObj.frontendId,
            encryption_method: parseInt(fileObj.encryptionMethod),
            created_at: fileObj.createdAt,
            duration: fileState.duration,
            iv: fileState.iv,
            key: fileState.key,
            crc: 0,
            fragments: []
         })
      }
      return this.backendState.get(fileObj.frontendId)
   }
   onFileMetadata(frontendId, field, current) {
      if (current && field) {
         let fileObj = this.uploadRuntime.getFileState(frontendId).fileObj
         let state = this.getOrCreateState(fileObj)
         if (field === "videoMetadata") {
            state.videoMetadata = current
         }
         else if (field === "rawMetadata") {
            state.rawMetadata = current
         }
      }
   }

   fillAttachmentInfo(attachment, discordResponse, discordAttachment) {
      const fileObj = attachment.fileObj
      const backendState = this.getOrCreateState(fileObj)
      const fileState = this.uploadRuntime.getFileState(fileObj.frontendId)

      if (attachment.type === attachmentType.file) {
         backendState.crc = (fileState.crc >>> 0)

         backendState.fragments.push({
            fragment_sequence: attachment.fragmentSequence,
            fragment_size: attachment.rawBlob.size,
            channel_id: discordResponse.data.channel_id,
            message_id: discordResponse.data.id,
            attachment_id: discordAttachment.id,
            message_author_id: discordResponse.data.author.id,
            offset: attachment.offset,
            crc: attachment.crc >>> 0
         })

         fileState.incrementChunk(fileObj.frontendId)

      } else if (attachment.type === attachmentType.thumbnail) {
         backendState.thumbnail = {
            size: attachment.rawBlob.size,
            channel_id: discordResponse.data.channel_id,
            message_id: discordResponse.data.id,
            attachment_id: discordAttachment.id,
            iv: attachment.iv,
            key: attachment.key,
            message_author_id: discordResponse.data.author.id
         }
         fileState.markThumbnailUploaded()

      } else if (attachment.type === attachmentType.subtitle) {
         backendState.subtitles ??= []
         backendState.subtitles.push({
            size: attachment.rawBlob.size,
            channel_id: discordResponse.data.channel_id,
            message_id: discordResponse.data.id,
            attachment_id: discordAttachment.id,
            language: attachment.subName,
            is_forced: attachment.isForced,
            iv: attachment.iv,
            key: attachment.key,
            message_author_id: discordResponse.data.author.id
         })
         console.log("fileState.extractedSubtitleCount: " + fileState.extractedSubtitleCount)
         console.log("backendState.subtitles.length: " + backendState.subtitles.length)
         if (fileState.extractedSubtitleCount === backendState.subtitles.length) {
            fileState.markSubtitlesUploaded()
         }
      }

      if (fileState.isFullyUploaded()) {
         fileState.markFileUploaded(fileObj.frontendId)
         this.backendState.delete(fileObj.frontendId)
         this.backendFileQueue.put(backendState)
      }
   }
}
