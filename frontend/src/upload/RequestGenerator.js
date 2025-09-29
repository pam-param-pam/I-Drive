import { create } from "@/api/folder.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, encryptionMethod, fileUploadStatus } from "@/utils/constants.js"
import { appendMp4BoxBuffer, generateIv, generateKey, isVideoFile, makeThumbnailIfNeeded, parseVideoMetadata, roundUpTo64 } from "@/upload/uploadHelper.js"
import { buf as crc32buf } from "crc-32"
import { v4 as uuidv4 } from "uuid"
import { showToast } from "@/utils/common.js"

export class RequestGenerator {
   constructor(backendManager) {
      this.uploadStore = useUploadStore()
      this.mainStore = useMainStore()
      this.createdFolders = new Map()
      this._generatorInstance = null
      this._MP4BoxPromise = null
      this.backendManager = backendManager
      this.mp4Boxes = new Map()
   }

   async getMp4Box() {
      if (!this._MP4BoxPromise) {
         this._MP4BoxPromise = import("mp4box")
      }
      return this._MP4BoxPromise
   }

   async getRequest() {
      if (this.uploadStore.pausedRequests.length > 0) {
         return this.uploadStore.pausedRequests.shift()
      } else {
         if (!this._generatorInstance) {
            this._generatorInstance = this.makeRequests()
         }

         const next = await this._generatorInstance.next()
         if (next.done) {
            this._generatorInstance = null
            return null
         }

         let request = next.value
         request.id = uuidv4()
         return request
      }
   }

   async* makeRequests() {
      /**
       this is a generator function!
       */

      const MP4Box = await this.getMp4Box()

      const maxChunkSize = this.mainStore.user.maxDiscordMessageSize
      const maxChunks = this.mainStore.user.maxAttachmentsPerMessage

      let totalSize = 0
      let attachments = []
      let queueFile
      while ((queueFile = this.uploadStore.getFileFromQueue())) {
         console.log("talking queue file")
         let frontendId = queueFile.fileObj.frontendId

         try {
            //creating folder if needed and getting it's backend ID
            queueFile.fileObj.folderId = await this.getOrCreateFolder(queueFile.fileObj)

            if (queueFile.fileObj.encryptionMethod !== encryptionMethod.NotEncrypted) {
               queueFile.fileObj.iv = generateIv(queueFile.fileObj.encryptionMethod)
               queueFile.fileObj.key = generateKey(queueFile.fileObj.encryptionMethod)
            }
            if (this.handleEmptyFile(queueFile)) continue

            let thumbnail = null
            //if this is true it means the thumbnail was already extracted, no need to do it again.
            if (!this.uploadStore.getFileState(frontendId)?.thumbnailExtracted) {
               thumbnail = await makeThumbnailIfNeeded(queueFile)
            }

            //if thumbnail exists we generate a request with them
            if (thumbnail) {
               this.uploadStore.markThumbnailExtracted(frontendId)

               //CASE 1, totalSize including thumbnail.size is > 10Mb or attachments.length == 10
               if (totalSize + thumbnail.size > maxChunkSize || attachments.length === 10) {
                  showToast("warning", "Couldn't fit thumbnail with 1st fragment for file: " + queueFile.fileObj.name)

                  let request = { "totalSize": totalSize, "attachments": attachments }
                  totalSize = 0
                  attachments = []
                  yield request
               }

               //else we add it
               let attachment = { "type": attachmentType.thumbnail, "fileObj": queueFile.fileObj, "rawBlob": thumbnail }
               if (queueFile.fileObj.encryptionMethod !== encryptionMethod.NotEncrypted) {
                  attachment.iv = generateIv(queueFile.fileObj.encryptionMethod)
                  attachment.key = generateKey(queueFile.fileObj.encryptionMethod)
               }

               attachments.push(attachment)
               //rounding to 64 as padding for encryption
               totalSize += roundUpTo64(thumbnail.size)
            }

            //If there's to little space left in the request, we yield to prevent, for example,
            // the beginning of a video having 0.5mb which would cause multiple messages
            // that have to be loaded before playback starts
            if (totalSize > maxChunkSize / 2 || attachments.length === 10) {
               let request = { "totalSize": totalSize, "attachments": attachments }
               totalSize = 0
               attachments = []
               yield request
            }


            //CASE 1.2 attachments are not created, we create chunked requests from the big file
            const state = this.uploadStore.getFileState(frontendId)

            let chunkSequence = state.extractedChunks
            let offset = state.offset || 0

            const fileSize = queueFile.fileObj.size

            let mp4boxFile = this.mp4Boxes.get(frontendId)
            //create mp4box only if needed
            if (isVideoFile(queueFile.fileObj.extension) && !mp4boxFile) {
               mp4boxFile = MP4Box.createFile()
               this.mp4Boxes.set(frontendId, mp4boxFile)
               this.uploadStore.markVideoMetadataRequired(frontendId)

               mp4boxFile.onReady = function(info) {
                  let videoMetadata = parseVideoMetadata(info)
                  this.backendManager.fillVideoMetadata(state.fileObj, videoMetadata)
                  this.uploadStore.markVideoMetadataExtracted(frontendId)
               }.bind(this)
            }

            while (offset < fileSize) {
               const remainingSpace = maxChunkSize - totalSize
               const remainingFileSize = fileSize - offset
               const chunkSizeToTake = Math.min(remainingSpace, remainingFileSize)
               const chunk = queueFile.systemFile.slice(offset, offset + chunkSizeToTake)

               if (mp4boxFile && !state.videoMetadataExtracted) {
                  appendMp4BoxBuffer(mp4boxFile, chunk, offset)
               }

               let attachment = {
                  "type": attachmentType.file,
                  "fileObj": queueFile.fileObj,
                  "rawBlob": chunk,
                  "fragmentSequence": chunkSequence + 1,
                  "offset": offset
               }

               attachments.push(attachment)
               totalSize += roundUpTo64(chunk.size)
               offset += chunk.size
               queueFile.fileObj.crc = crc32buf(new Uint8Array(await chunk.arrayBuffer()), queueFile.fileObj.crc) //todo move crc to state?
               chunkSequence++
               this.uploadStore.onNewFileChunk(frontendId, offset, chunkSequence)

               // we have to yield
               if (totalSize >= maxChunkSize || attachments.length >= maxChunks - 1) {
                  yield { "totalSize": totalSize, "attachments": attachments }
                  totalSize = 0
                  attachments = []
               }

            }
            //we need to inform about totalChunks of a file
            this.uploadStore.setTotalChunks(frontendId, chunkSequence)

            if (mp4boxFile) {
               mp4boxFile.flush()
               this.mp4Boxes.delete(frontendId)
               this.uploadStore.markVideoMetadataExtracted(frontendId) //yes this needs to be here
            }

         } catch (err) {
            if (err.name === "NotFoundError") {
               this.uploadStore.setStatus(frontendId, fileUploadStatus.fileGone)
            } else {
               this.uploadStore.setStatus(frontendId, fileUploadStatus.errorOccurred)
               this.uploadStore.setError(frontendId, err)
            }
            throw err

         }
      }
      //we need to handle the already created attachments after break
      if (attachments.length > 0) {
         const request = { "totalSize": totalSize, "attachments": attachments }
         yield request
      }

   }

   async getOrCreateFolder(fileObj) {
      let path = fileObj.path
      if (path === "") {
         return fileObj.folderContext
      }

      // Split path into parts (e.g., ["folder_1", "folder_2", "folder_3"])
      let pathParts = path.split("/")

      let parentFolder = fileObj.folderContext
      for (let i = 1; i <= pathParts.length; i++) {
         // idziemy od tyłu po liscie czyli jesli lista to np [a1, b2, c3, d4, e5, f6]
         // to najpierw bedziemy mieli a1
         // potem a1, b2
         // potem a1, b2, c3
         let path_key = fileObj.uploadId + pathParts.slice(0, i).join("/")
         if (this.createdFolders[path_key]) {
            parentFolder = this.createdFolders[path_key]
         } else {
            let folderName = pathParts.slice(0, i)[pathParts.slice(0, i).length - 1]

            let folder = await create({ "parent_id": parentFolder, "name": folderName }, {
               __retryErrors: true
            })
            parentFolder = folder.id
            this.createdFolders[path_key] = folder.id
         }
      }
      return parentFolder
   }

   handleEmptyFile(queueFile) {
      if (queueFile.fileObj.size === 0) {
         this.uploadStore.markFileUploaded(queueFile.fileObj.frontendId)
         let file = this.backendManager.getOrCreateState(queueFile.fileObj)
         this.backendManager.addFinishedFile(file)
         this.backendManager.saveFilesIfNeeded()
         return true
      }
      return false
   }
}
