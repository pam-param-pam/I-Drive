import { fileUploadStatus } from "@/utils/constants.js"
import { isErrorStatus } from "@/upload/utils/uploadHelper.js"

export class FileStateHolder {
   constructor(file, fieldChangeCallback) {
      this.fileObj = file.fileObj
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

      this.status = fileUploadStatus.preparing
      this.progress = 0
      this.uploadedBytes = 0
      this.offset = 0
      this.error = null

      this.rawMetadata = null
      this.duration = 0
      this.crc = 0
      this.videoMetadata = null
      this.iv = undefined
      this.key = undefined

      this._fieldChangeCallback = fieldChangeCallback
   }

   emitInitialState() {
      for (const field of Object.keys(this)) {
         if (field.startsWith("_")) continue

         this._fieldChangeCallback?.({
            frontendId: this.frontendId,
            field,
            prev: undefined,
            current: this[field]
         })
      }
   }

   _set(field, value) {
      if (this[field] === value) return

      const prev = this[field]
      this[field] = value

      this._fieldChangeCallback?.({
         frontendId: this.frontendId,
         field,
         prev,
         current: value
      })
   }

   incrementChunk() {
      this._set("uploadedChunks", this.uploadedChunks + 1)
   }

   markThumbnailUploaded() {
      this._set("thumbnailUploaded", true)
   }

   markThumbnailExtracted() {
      this._set("thumbnailExtracted", true)
   }

   markVideoMetadataRequired() {
      this._set("videoMetadataRequired", true)
   }

   markVideoMetadataExtracted() {
      this._set("videoMetadataExtracted", true)
   }

   markSubtitlesRequired() {
      this._set("subtitlesRequired", true)
   }

   markSubtitlesExtracted() {
      this._set("subtitlesExtracted", true)
   }

   markSubtitlesUploaded() {
      this._set("subtitlesUploaded", true)
   }
   setExpectedSubtitleCount(count) {
      this._set("expectedSubtitleCount", count)
   }
   incrementExtractedSubtitleCount() {
      this._set("extractedSubtitleCount", this.extractedSubtitleCount+1)
   }
   setTotalChunks(count) {
      this._set("totalChunks", count)
   }

   updateUploadedBytes(bytesUploaded) {
      this._set("uploadedBytes", this.uploadedBytes + bytesUploaded)
      this.updateProgress()
   }

   setUploadedBytes(bytesUploaded) {
      this._set("uploadedBytes", bytesUploaded)
      this.updateProgress()
   }

   updateProgress() {
      const progress = Math.min(100, Math.floor((this.uploadedBytes / this.fileObj.size) * 100))
      this._set("progress", progress)
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
   setDuration(value) {
      this._set("duration", value)
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
   setStatus(status) {
      if (this.status === fileUploadStatus.errorOccurred && status !== fileUploadStatus.retrying) {
         console.warn("Possible override of error status!")
         console.log(this.error)
      }
      this._set("error", null)
      this._set("status", status)
   }

   setError(error) {
      this._set("error", error)
   }


   markFileUploaded() {
      this.setStatus(fileUploadStatus.uploaded)
      setTimeout(() => {
         if (this.status !== fileUploadStatus.uploaded) return
         this.setStatus(fileUploadStatus.waitingForSave)
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
         !this.subtitlesRequired || //base case, no subs
         (this.subtitlesRequired && this.subtitlesExtracted && this.subtitlesUploaded) || //subs exist, are required and must be uploaded
         (this.subtitlesRequired && !this.subtitlesExtracted && this.isFullySplit()) // subs apparently exist, but extraction failed indicated by the fact that file is fully split and this.subtitlesExtracted is still false

      // console.log("uploadedChunks: " + this.uploadedChunks)
      // console.log("totalChunks: " + this.totalChunks)
      //
      // console.log("chunksDone: " + chunksDone)
      // console.log("thumbnailDone: " + thumbnailDone)
      // console.log("videoMetadataDone: " + videoMetadataDone)
      // console.log("filledInfo: " + filledInfo)
      // console.log("subtitlesDone: " + subtitlesDone)
      // console.log("isFullySplit: " + this.isFullySplit())

      return (chunksDone && thumbnailDone && videoMetadataDone && filledInfo && subtitlesDone) || this.fileObj.size === 0
   }

   isErrorStatus() {
      return isErrorStatus(this.status)
   }

}
