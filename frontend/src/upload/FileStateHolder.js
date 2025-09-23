import { fileUploadStatus } from "@/utils/constants.js"

export class FileStateHolder {
   constructor(fileObj) {
      this.frontendId = fileObj.frontendId
      this.totalChunks = -1
      this.uploadedChunks = 0
      this.thumbnailUploaded = false
      this.videoMetadataExtracted = false
      this.thumbnailRequired = false
      this.videoMetadataRequired = false

      this.status = fileUploadStatus.preparing
      this.progress = 0
      this.fileObj = fileObj

      this.error = null
   }

   incrementChunk() {
      this.uploadedChunks += 1
   }

   markThumbnailUploaded() {
      this.thumbnailUploaded = true
   }

   markThumbnailRequired() {
      this.thumbnailRequired = true
   }

   markVideoMetadataRequired() {
      this.videoMetadataRequired = true

   }

   markVideoMetadataExtracted() {
      this.videoMetadataExtracted = true
   }


   isFullyUploaded() {
      const chunksDone = this.uploadedChunks === this.totalChunks
      const thumbnailDone = !this.thumbnailRequired || this.thumbnailUploaded
      const videoMetadataDone = !this.videoMetadataRequired || this.videoMetadataExtracted
      const filledInfo = this.totalChunks !== -1

      return chunksDone && thumbnailDone && videoMetadataDone && filledInfo
   }

   setTotalChunks(count) {
      this.totalChunks = count
   }
}
