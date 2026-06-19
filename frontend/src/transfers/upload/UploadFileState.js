import { isErrorStatus } from "@/transfers/upload/utils/uploadHelper.js"
import { uploadFileStatus } from "@/transfers/upload/constants.js"
import { BaseTransferFileState } from "@/transfers/shared/base/BaseTransferFileState.js"

export class UploadFileState extends BaseTransferFileState {
   constructor(file, fieldChangeCallback) {
      const fileObj = file.fileObj

      super(fileObj.frontendId, fieldChangeCallback, {
         initialStatus: uploadFileStatus.preparing,
         size: fileObj.size,
         retryStatus: uploadFileStatus.retrying,
         isErrorStatus
      })

      this.fileObj = fileObj
      this.systemFile = file.systemFile
      this.frontendId = this.fileObj.frontendId

      this.totalChunks = undefined
      this.extractedChunks = 0
      this.uploadedChunks = 0

      this.thumbnailExtracted = undefined
      this.thumbnailUploaded = false

      this.videoMetadataRequired = undefined
      this.videoMetadataExtracted = false
      this.subtitlesRequired = undefined
      this.subtitlesExtracted = false
      this.subtitlesUploaded = false
      this.expectedSubtitleCount = 0
      this.extractedSubtitleCount = 0

      this.offset = 0

      this.rawMetadata = null
      this.photoMetadata = null
      this.crc = 0
      this.videoMetadata = null
      this.iv = undefined
      this.key = undefined

      this._waitingTimer = null
   }

   incrementChunk() {
      this._increment("uploadedChunks")
   }

   markThumbnailUploaded() {
      this._mark("thumbnailUploaded")
   }

   markThumbnailExtracted() {
      this._mark("thumbnailExtracted")
   }

   markVideoMetadataRequired() {
      this._mark("videoMetadataRequired")
   }

   markVideoMetadataExtracted() {
      this._mark("videoMetadataExtracted")
   }

   markSubtitlesRequired() {
      this._mark("subtitlesRequired")
   }

   markSubtitlesExtracted() {
      this._mark("subtitlesExtracted")
   }

   markSubtitlesUploaded() {
      this._mark("subtitlesUploaded")
   }

   setExpectedSubtitleCount(count) {
      this._set("expectedSubtitleCount", count)
   }

   incrementExtractedSubtitleCount() {
      this._increment("extractedSubtitleCount")
   }

   setTotalChunks(count) {
      this._set("totalChunks", count)
   }

   onNewFileChunk(offset, extractedChunks) {
      this._set("offset", offset)
      this._set("extractedChunks", extractedChunks)
   }

   setVideoMetadata(value) {
      this._set("videoMetadata", value)
   }

   setRawMetadata(value) {
      this._set("rawMetadata", value)
   }

   setPhotoMetadata(value) {
      this._set("photoMetadata", value)
   }

   setCrc(value) {
      this._set("crc", value)
   }

   setKey(key) {
      this._set("key", key)
   }

   setIv(iv) {
      this._set("iv", iv)
   }

   markFileUploaded() {
      this.setStatus(uploadFileStatus.uploaded)
      this._waitingTimer = setTimeout(() => {
         if (this.status !== uploadFileStatus.uploaded) return
         this.setStatus(uploadFileStatus.waitingForSave)
      }, 1500)
   }

   isFullySplit() {
      return this.extractedChunks === this.totalChunks
   }

   areSecretsGenerated() {
      return this.iv !== undefined && this.key !== undefined
   }

   isFullyUploaded() {
      const chunksDone = this.uploadedChunks === this.totalChunks
      const thumbnailDone = !this.thumbnailExtracted || this.thumbnailUploaded
      const videoMetadataDone = !this.videoMetadataRequired || this.videoMetadataExtracted || this.isFullySplit()
      const filledInfo = this.totalChunks !== undefined

      const subtitlesDone =
         !this.subtitlesRequired ||
         (this.subtitlesRequired && this.subtitlesExtracted && this.subtitlesUploaded) ||
         (this.subtitlesRequired && !this.subtitlesExtracted && this.isFullySplit())

      return (chunksDone && thumbnailDone && videoMetadataDone && filledInfo && subtitlesDone) || this.fileObj.size === 0
   }

   onDelete() {
      if (this._waitingTimer) {
         clearTimeout(this._waitingTimer)
         this._waitingTimer = null
      }
   }
}