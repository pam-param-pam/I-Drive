import { PipelineWorker } from "@/transfers/shared/base/PipelineWorker.js"
import { workerExitReason } from "@/transfers/shared/constants.js"
import { attachmentType } from "@/transfers/upload/constants.js"

export class DiscordResponseStage extends PipelineWorker {
   constructor({ discordResponseQueue, backendFileQueue, uploadRuntime }) {
      super()

      this.discordResponseQueue = discordResponseQueue
      this.backendFileQueue = backendFileQueue
      this.uploadRuntime = uploadRuntime

      this.backendState = new Map()

      this._metadataListener = ({ frontendId, field, current }) => {
         this.onFileMetadata(frontendId, field, current)
      }

      this._unsubscribe = this.uploadRuntime.onFileChange(["videoMetadata"], this._metadataListener)
   }

   async run() {
      if (this._running) {
         console.warn("DiscordResponseConsumer is already running!")
         return workerExitReason.stopped
      }

      const signal = this._markStarted()
      let exitReason = workerExitReason.stopped

      try {
         while (!signal.aborted) {
            if (this._stopRequested) {
               exitReason = workerExitReason.stopped
               break
            }

            const result = await this.takeWithAbort(this.discordResponseQueue, signal)

            if (!result) {
               exitReason = workerExitReason.inputEnded
               break
            }

            await this.handleDiscordResult(result, signal)
         }

         if (exitReason === workerExitReason.inputEnded) {
            this.backendFileQueue.close()
         }

         if (this._killed) {
            exitReason = workerExitReason.killed
         }

         return exitReason
      } catch (err) {
         exitReason = this._handleRunError(err)
         return exitReason
      } finally {
         this._unsubscribeMetadataListener()
         this._markFinished(exitReason)
      }
   }

   _unsubscribeMetadataListener() {
      if (this._unsubscribe) {
         this._unsubscribe()
         this._unsubscribe = null
      }
   }

   async handleDiscordResult({ request, discordResponse }, signal) {
      for (let i = 0; i < request.attachments.length; i++) {
         const attachment = request.attachments[i]
         const discordAttachment = discordResponse.data.attachments[i]
         await this.fillAttachmentInfo(attachment, discordResponse, discordAttachment, signal)
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
            iv: fileState.iv,
            key: fileState.key,
            crc: 0,
            fragments: [],
            photoMetadata: fileState.photoMetadata,
            rawMetadata: fileState.rawMetadata
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
         } else {
            throw Error("Unknown metadata field")
         }
      }
   }

   async fillAttachmentInfo(attachment, discordResponse, discordAttachment, signal) {
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
         if (fileState.extractedSubtitleCount === backendState.subtitles.length) {
            fileState.markSubtitlesUploaded()
         }
      }

      if (fileState.isFullyUploaded()) {
         fileState.markFileUploaded(fileObj.frontendId)
         this.backendState.delete(fileObj.frontendId)
         await this.putWithAbort(this.backendFileQueue, backendState, signal)
      }
   }
}