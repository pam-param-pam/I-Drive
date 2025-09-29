import { fileUploadStatus } from "@/utils/constants.js"

export class FileStateHolder {
   constructor(file) {
      this.fileObj = file.fileObj
      this.systemFile = file.systemFile
      this.frontendId = this.fileObj.frontendId
      this.totalChunks = undefined
      this.extractedChunks = 0
      this.uploadedChunks = 0
      this.thumbnailUploaded = false
      this.videoMetadataExtracted = false
      this.thumbnailExtracted = undefined
      this.videoMetadataRequired = undefined

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


   isFullyUploaded() {
      const chunksDone = this.uploadedChunks === this.totalChunks
      const thumbnailDone = !this.thumbnailExtracted || this.thumbnailUploaded
      const videoMetadataDone = !this.videoMetadataRequired || this.videoMetadataExtracted
      const filledInfo = this.totalChunks !== undefined

      return (chunksDone && thumbnailDone && videoMetadataDone && filledInfo) || this.fileObj.size === 0
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
