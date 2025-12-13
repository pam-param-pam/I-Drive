import { attachmentType, fileUploadStatus } from "@/utils/constants.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { createFile } from "@/api/files.js"
import { showToast } from "@/utils/common.js"

export class BackendManager {
   constructor() {
      this.uploadStore = useUploadStore()
      this.backendState = new Map()
      this.finishedFiles = []
      this.failedFiles = []
      this.databaseErrors = 0
   }

   async afterUploadRequest(request, discordResponse) {
      for (let i = 0; i < request.attachments.length; i++) {
         let attachment = request.attachments[i]
         let discordAttachment = discordResponse.data.attachments[i]
         await this.fillAttachmentInfo(attachment, discordResponse, discordAttachment)
      }
      this.uploadStore.markRequestFinished(request)
   }

   addFinishedFile(file) {
      const exists = this.finishedFiles.some(f => f.frontend_id === file.frontend_id)
      if (!exists) {
         this.finishedFiles.push(file)
      } else {
         console.warn(`File with frontend_id ${file.frontend_id} is already in finishedFiles`)
      }
   }

   getOrCreateState(fileObj) {
      if (!this.backendState.has(fileObj.frontendId)) {
         let file_data = {
            "name": fileObj.name,
            "parent_id": fileObj.folderId,
            "extension": fileObj.extension,
            "size": fileObj.size,
            "frontend_id": fileObj.frontendId,
            "encryption_method": parseInt(fileObj.encryptionMethod),
            "created_at": fileObj.createdAt,
            "duration": fileObj.duration,
            "iv": fileObj.iv,
            "key": fileObj.key,
            "crc": 0,
            "parent_password": fileObj.parentPassword, //this is later removed!
            "lock_from": fileObj.lockFrom, //this is later removed!
            "attachments": []
         }

         this.backendState.set(fileObj.frontendId, file_data)
      }
      return this.backendState.get(fileObj.frontendId)

   }

   fillVideoMetadata(fileObj, videoMetadata) {
      let state = this.getOrCreateState(fileObj)
      state.videoMetadata = {
         "mime": videoMetadata.mime,
         "is_progressive": videoMetadata.is_progressive,
         "is_fragmented": videoMetadata.is_fragmented,
         "has_moov": videoMetadata.has_moov,
         "has_IOD": videoMetadata.has_IOD,
         "brands": videoMetadata.brands,
         "video_tracks": videoMetadata.video_tracks,
         "audio_tracks": videoMetadata.audio_tracks,
         "subtitle_tracks": videoMetadata.subtitle_tracks
      }
   }

   fillAttachmentInfo(attachment, discordResponse, discordAttachment) {
      let fileObj = attachment.fileObj
      let state = this.getOrCreateState(fileObj)

      if (attachment.type === attachmentType.file) {
         this.uploadStore.incrementChunk(fileObj.frontendId)
         let crc = fileObj.crc || 0
         state.crc = crc >>> 0
         let attachment_data = {
            "fragment_sequence": attachment.fragmentSequence,
            "fragment_size": attachment.rawBlob.size,
            "channel_id": discordResponse.data.channel_id,
            "message_id": discordResponse.data.id,
            "attachment_id": discordAttachment.id,
            "message_author_id": discordResponse.data.author.id,
            "offset": attachment.offset
         }
         state.attachments.push(attachment_data)
      } else if (attachment.type === attachmentType.thumbnail) {
         state.thumbnail = {
            "size": attachment.rawBlob.size,
            "channel_id": discordResponse.data.channel_id,
            "message_id": discordResponse.data.id,
            "attachment_id": discordAttachment.id,
            "iv": attachment.iv,
            "key": attachment.key,
            "message_author_id": discordResponse.data.author.id
         }
         this.uploadStore.markThumbnailUploaded(fileObj.frontendId)

      } else if (attachment.type === attachmentType.subtitle) {
         state.subtitles = state.subtitles || []
         state.subtitles.push({
            "size": attachment.rawBlob.size,
            "channel_id": discordResponse.data.channel_id,
            "message_id": discordResponse.data.id,
            "attachment_id": discordAttachment.id,
            "language": attachment.subName,
            "is_forced": attachment.isForced,
            "iv": attachment.iv,
            "key": attachment.key,
            "message_author_id": discordResponse.data.author.id
         })
         this.uploadStore.markSubtitlesUploaded(fileObj.frontendId)

      }
      this.backendState.set(fileObj.frontendId, state)

      let isFinished = this.uploadStore.isFileUploaded(fileObj.frontendId)
      if (isFinished) {
         this.addFinishedFile(state)
         this.backendState.delete(fileObj.frontendId)
         this.uploadStore.markFileUploaded(fileObj.frontendId)
      }

      this.saveFilesIfNeeded()

   }

   async saveFilesIfNeeded() {
      let totalSize = 0

      for (const file of this.finishedFiles) {
         totalSize += file.size
      }

      if (this.finishedFiles.length > 20 || totalSize > 100 * 1024 * 1024 || this.uploadStore.areAllUploadsFinished) {
         let finishedFiles = this.finishedFiles
         this.finishedFiles = []
         this.saveFiles(finishedFiles)
      }

   }

   saveFiles(finishedFiles) {
      const seenIds = new Set()
      const resourcePasswords = {}

      for (let file of finishedFiles) {

         const { lock_from, parent_password } = file
         if (parent_password && lock_from) {
            seenIds.add(lock_from)
            if (parent_password) {
               resourcePasswords[lock_from] = parent_password
            }
         }

      }
      createFile({ files: finishedFiles, resourcePasswords: resourcePasswords }, { __displayErrorToast: false })
         .then(() => {
            this.onBackendSave(finishedFiles)
         })
         .catch((error) => {
            this.onBackendSaveError(finishedFiles, error)
         })
   }

   onBackendSaveError(finishedFiles, error) {
      for (let file of finishedFiles) {
         this.uploadStore.setStatus(file.frontend_id, fileUploadStatus.saveFailed)
         this.uploadStore.setError(file.frontend_id, error?.response?.data)
         this.failedFiles.push(file)
      }
      if (this.databaseErrors > 2) {
         showToast("error", "toasts.databaseIsLockedUploadPaused")
         this.uploadStore.pauseAll()
         this.databaseErrors = 0
      }
      if (error.response.status >= 500) this.databaseErrors++
   }

   onBackendSave(finishedFiles) {
      for (let file of finishedFiles) {
         this.uploadStore.markFileSaved(file.frontend_id)
      }
      this.databaseErrors = Math.max(this.databaseErrors - 1, 0)
      this.uploadStore.onUploadFinish()
   }

   reSaveFile(frontendId) {
      //tdodo this is buggy
      const filesToResave = this.failedFiles.slice(0, Math.min(20, this.failedFiles.length))

      // Retry each file after a delay
      filesToResave.forEach((failedFile) => {
         const frontendId = failedFile.frontend_id
         this.uploadStore.setStatus(frontendId, fileUploadStatus.retrying)
      })
      setTimeout(() => {
         this.saveFiles(filesToResave)
      }, 1000)
   }
}