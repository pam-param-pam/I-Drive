import { fileUploadStatus } from "@/utils/constants.js"

export class FileStateHolder {
   constructor(file) {
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

      this.status = fileUploadStatus.preparing
      this.progress = 0
      this.uploadedBytes = 0
      this.offset = 0
      this.error = null
   }

   incrementChunk() {
      this.uploadedChunks += 1
   }

   markThumbnailUploaded() {
      this.thumbnailUploaded = true
   }

   markThumbnailExtracted() {
      this.thumbnailExtracted = true
   }

   markVideoMetadataRequired() {
      this.videoMetadataRequired = true
   }

   markVideoMetadataExtracted() {
      this.videoMetadataExtracted = true
   }

   markSubtitlesRequired() {
      this.subtitlesRequired = true
   }

   markSubtitlesExtracted() {
      this.subtitlesExtracted = true
   }

   markSubtitlesUploaded() {
      this.subtitlesUploaded = true
   }

   isFullySplit() {
      return this.extractedChunks === this.totalChunks
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


      console.log("subtitlesRequired: " + this.subtitlesRequired)
      console.log("subtitlesExtracted: " + this.subtitlesExtracted)
      console.log("subtitlesUploaded: " + this.subtitlesUploaded)
      console.log("isFullySplit: " + this.isFullySplit())

      return (chunksDone && thumbnailDone && videoMetadataDone && filledInfo && subtitlesDone) || this.fileObj.size === 0
   }

   setTotalChunks(count) {
      this.totalChunks = count
   }

   updateUploadedBytes(bytesUploaded) {
      this.uploadedBytes += bytesUploaded
      this.updateProgress()

   }

   setUploadedBytes(bytesUploaded) {
      this.uploadedBytes = bytesUploaded
      this.updateProgress()
   }

   updateProgress() {
      this.progress = Math.min(
         100,
         Math.floor((this.uploadedBytes / this.fileObj.size) * 100)
      )
   }
}
