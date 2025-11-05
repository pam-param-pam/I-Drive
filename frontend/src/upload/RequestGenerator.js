import { create } from "@/api/folder.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, encryptionMethod, fileUploadStatus } from "@/utils/constants.js"
import {
   appendMp4BoxBuffer,
   generateIv,
   generateKey,
   isVideoFile,
   makeThumbnailIfNeeded,
   parseVideoMetadata,
   roundUpTo64
} from "@/upload/utils/uploadHelper.js"
import { buf as crc32buf } from "crc-32"
import { v4 as uuidv4 } from "uuid"
import { showToast } from "@/utils/common.js"
import { getUploader } from "@/upload/Uploader.js"
import { buildVttFromSamples } from "@/utils/subtitleUtlis.js"

export class RequestGenerator {
   constructor(backendManager) {
      this.uploadStore = useUploadStore()
      this.mainStore = useMainStore()
      this.createdFolders = new Map()
      this._generatorInstance = null
      this._MP4BoxPromise = null
      this.backendManager = backendManager
      this.mp4Boxes = new Map()

      this.subtitleAttachments = new Map()
      this.subsNumTracker = new Map()
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

         const start = Date.now()
         const next = await this._generatorInstance.next()
         console.log(`Request took ${Date.now() - start} ms to complete.`)

         if (next.done) {
            this._generatorInstance = null
            return null
         }

         let request = next.value
         request.id = uuidv4()
         return request
      }
   }
   //todo clean this, make this function not be 180 lines long
   //todo check for possible race conditions with fileObj / state missing in mp4box callback functions


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

               attachments.push(attachment)
               //rounding to 64 as padding for encryption
               totalSize += roundUpTo64(thumbnail.size)
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
               mp4boxFile.onError = function (e) {
                  console.log('Received Error Message ' + e);
               };
               mp4boxFile.onReady = function(info) {
                  console.log("ON READY")
                  console.log(info)

                  let videoMetadata = parseVideoMetadata(info)
                  this.backendManager.fillVideoMetadata(state.fileObj, videoMetadata)
                  this.uploadStore.markVideoMetadataExtracted(frontendId)

                  let subtitleTracks = info.tracks.filter(t => t.type === "subtitles") || []
                  this.setSubsNumber(frontendId, subtitleTracks.length)
                  if (subtitleTracks.length > 0) {
                     console.log("markSubtitlesRequired")
                     this.uploadStore.markSubtitlesRequired(frontendId)
                  }

                  subtitleTracks.forEach(subTrack => {
                     mp4boxFile.setExtractionOptions(subTrack.id, subTrack, { nbSamples: subTrack.nb_samples })
                  })
                  mp4boxFile.start()

               }.bind(this)

               mp4boxFile.onSamples = function(id, subTrack, samples) {
                  console.log("ON SAMPLES")
                  if (!samples?.length) return

                  if (!mp4boxFile.collectedSamples) mp4boxFile.collectedSamples = []
                  mp4boxFile.collectedSamples.push(...samples)

                  let collected = mp4boxFile.collectedSamples.length
                  let total = subTrack.nb_samples

                  if (collected >= total) {
                     let vttBlob = buildVttFromSamples(subTrack, mp4boxFile.collectedSamples)
                     if (vttBlob.size > maxChunkSize) return
                     mp4boxFile.collectedSamples = []
                     let name = subTrack.name || subTrack.language || id
                     this.createAndPushSubtitleAttachment(frontendId, vttBlob, name)
                  }
                  mp4boxFile.start()
               }.bind(this)
            }

            while (offset < fileSize) {
               const remainingSpace = maxChunkSize - totalSize
               const remainingFileSize = fileSize - offset
               const chunkSizeToTake = Math.min(remainingSpace, remainingFileSize)
               const chunk = queueFile.systemFile.slice(offset, offset + chunkSizeToTake)


               //If there's to little space left in the request, we yield to prevent, for example,
               // the beginning of a video having 0.5mb which would cause multiple messages
               // that have to be loaded before playback starts
               if ((remainingSpace < maxChunkSize / 3 && remainingFileSize > maxChunkSize / 3) || attachments.length === 10) {
                  let request = { "totalSize": totalSize, "attachments": attachments }
                  totalSize = 0
                  attachments = []
                  yield request
               }


               if (mp4boxFile && (!state.videoMetadataExtracted || !state.subtitlesExtracted)) {
                  appendMp4BoxBuffer(mp4boxFile, chunk, offset)
               }
               else {
                  //todo flush... and unsetExtractionOptions
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
            console.log("setTotalChunks")
            setTimeout(() => {
               //we need to inform about totalChunks of a file
               this.uploadStore.setTotalChunks(frontendId, chunkSequence)
               this.cleanMp4Box(mp4boxFile, frontendId)

            }, 25)


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

   setSubsNumber(frontendId, number) {
      this.subsNumTracker.set(frontendId, number)
   }
   createAndPushSubtitleAttachment(frontendId, blob, subName) {
      console.log("createAndPushSubtitleAttachment")
      const state = this.uploadStore.getFileState(frontendId)
      const fileObj = state.fileObj
      let attachment = { "type": attachmentType.subtitle, "fileObj": fileObj, "rawBlob": blob, "subName": subName }

      if (!this.subtitleAttachments.has(frontendId)) {
         this.subtitleAttachments.set(frontendId, [])
      }
      this.subtitleAttachments.get(frontendId).push(attachment)

      this.addSubsToUploadIfNeeded(frontendId)

   }
   addSubsToUploadIfNeeded(frontendId) {
      const maxMessageSize = this.mainStore.user.maxDiscordMessageSize
      const maxAttachments = this.mainStore.user.maxAttachmentsPerMessage

      let attachments = this.subtitleAttachments.get(frontendId)
      if (this.subsNumTracker.get(frontendId) !== attachments.length) return
      let totalSize = 0

      for (let attachment of attachments) {
         totalSize += attachment.rawBlob.size
      }
      if (totalSize >= maxMessageSize || attachments.length > maxAttachments) {
         showToast("error", "toasts.tooManySubtitlesOrTooBig")
         this.uploadStore.markSubtitlesUploaded(frontendId)
         return
      }

      this.uploadStore.markSubtitlesExtracted(frontendId)

      let request = { "totalSize": totalSize, "attachments": attachments }

      this.uploadStore.addPausedRequest(request)
      getUploader().processUploads()


   }
   cleanMp4Box(mp4boxFile, frontendId) {
      if (mp4boxFile) {
         mp4boxFile.flush()
         this.mp4Boxes.delete(frontendId)
         this.subsNumTracker.delete(frontendId)
         this.subtitleAttachments.delete(frontendId)
      }
   }
}
