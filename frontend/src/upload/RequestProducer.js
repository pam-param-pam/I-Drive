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
import { buildVttFromSamples } from "@/utils/subtitleUtlis.js"
import { getUploader } from "@/upload/Uploader.js"

export class RequestProducer {
   constructor({ uploadRuntime, fileQueue, requestQueue, requestMoreFiles }) {
      this.uploadStore = useUploadStore()
      this.mainStore = useMainStore()
      this.uploadRuntime = uploadRuntime
      this.fileQueue = fileQueue
      this.requestQueue = requestQueue
      this.requestMoreFiles = requestMoreFiles

      this.createdFolders = new Map()
      this.mp4Boxes = new Map()
      this.subtitleAttachments = new Map()
      this.subtitleNames = new Map()
      this.goneFiles = []

      this._MP4BoxPromise = null
      this._running = false
   }

   async getMp4Box() {
      if (!this._MP4BoxPromise) {
         this._MP4BoxPromise = import("mp4box")
      }
      return this._MP4BoxPromise
   }

   isRunning() {
      return this._running
   }

   async run() {
      if (this._running) {
         console.warn("RequestProducer is already running!")
         return
      }
      this._running = true

      const MP4Box = await this.getMp4Box()

      const maxChunkSize = this.mainStore.user.maxDiscordMessageSize
      const maxChunks = this.mainStore.user.maxAttachmentsPerMessage

      let totalSize = 0
      let attachments = []

      while (true) {
         this.requestMoreFiles()
         const queueFile = await this.fileQueue.take()
         if (!queueFile) {
            console.warn("RequestProducer breaking!")
            break
         }
         if (!queueFile) break   // queue closed

         const frontendId = queueFile.fileObj.frontendId
         const state = this.uploadRuntime.getFileState(frontendId)

         try {
            queueFile.fileObj.folderId = await this.getOrCreateFolder(queueFile.fileObj)

            if (queueFile.fileObj.encryptionMethod !== encryptionMethod.NotEncrypted && !state.areSecretsGenerated()) {
               state.setIv(generateIv(queueFile.fileObj.encryptionMethod))
               state.setKey(generateKey(queueFile.fileObj.encryptionMethod))
            }

            if (this.handleEmptyFile(queueFile)) {
               continue
            }

            // ---------- THUMBNAIL ----------
            if (!state.thumbnailExtracted) {
               const { thumbnail, other } = await makeThumbnailIfNeeded(queueFile)
               if (other) {
                  if (other.duration) state.setDuration(other.duration)
                  if (other.rawMetadata) state.setRawMetadata(other.rawMetadata)
               }
               if (thumbnail) {
                  state.markThumbnailExtracted(frontendId)

                  if (totalSize + thumbnail.size > maxChunkSize || attachments.length === maxChunks) {
                     showToast("warning", "Couldn't fit thumbnail with 1st fragment for file: " + queueFile.fileObj.name)
                     await this.requestQueue.put({ id: uuidv4(), totalSize, attachments })
                     totalSize = 0
                     attachments = []
                  }

                  attachments.push({ type: attachmentType.thumbnail, fileObj: queueFile.fileObj, rawBlob: thumbnail })
                  totalSize += roundUpTo64(thumbnail.size)
               }
            }

            // ---------- MP4 BOX HANDLING ----------
            let mp4boxFile = this.mp4Boxes.get(frontendId)
            if (isVideoFile(queueFile.fileObj.extension) && !mp4boxFile) {
               mp4boxFile = MP4Box.createFile()
               this.mp4Boxes.set(frontendId, mp4boxFile)
               state.markVideoMetadataRequired()

               mp4boxFile.onReady = info => {
                  const videoMetadata = parseVideoMetadata(info)
                  state.setVideoMetadata(videoMetadata)
                  state.markVideoMetadataExtracted()

                  const subtitleTracks = info.tracks.filter(t => t.type === "subtitles") || []
                  state.setExpectedSubtitleCount(subtitleTracks.length)
                  if (subtitleTracks.length > 0) {
                     state.markSubtitlesRequired()
                  }
                  subtitleTracks.forEach(track => {
                     mp4boxFile.setExtractionOptions(track.id, track, {
                        nbSamples: track.nb_samples
                     })
                  })
                  mp4boxFile.start()
               }

               mp4boxFile.onSamples = async (id, subTrack, samples) => {
                  if (!samples?.length) return

                  if (!mp4boxFile.collectedSamples) {
                     mp4boxFile.collectedSamples = []
                  }

                  mp4boxFile.collectedSamples.push(...samples)

                  if (mp4boxFile.collectedSamples.length >= subTrack.nb_samples) {
                     const vtt = buildVttFromSamples(subTrack, mp4boxFile.collectedSamples)
                     console.log(subTrack)
                     if (vtt.size <= maxChunkSize) {
                        let name
                        if (subTrack.language === "und" && subTrack.name === "SubtitleHandler") {
                           name = "" + id
                        } else if (subTrack.name === "SubtitleHandler") {
                           name = subTrack.language
                        } else if (subTrack.language === "und") {
                           name = subTrack.name
                        }
                        name = this.makeUniqueSubName(name, id)
                        let isForced = subTrack.kind?.value === "forced-subtitle"
                        this.createAndPushSubtitleAttachment(frontendId, vtt, name, isForced)
                     }
                  }
                  mp4boxFile.collectedSamples = []
               }
            }

            // ---------- FILE CHUNKS ----------
            let chunkSequence = state.extractedChunks || 0
            let offset = state.offset || 0
            const fileSize = queueFile.fileObj.size

            while (offset < fileSize) {
               const remainingSpace = maxChunkSize - totalSize
               const remainingFileSize = fileSize - offset
               const chunkSizeToTake = Math.min(remainingSpace, remainingFileSize)
               const chunk = queueFile.systemFile.slice(offset, offset + chunkSizeToTake)
               const buf = await chunk.arrayBuffer()
               if ((remainingSpace < maxChunkSize / 3 && remainingFileSize > maxChunkSize / 3) || attachments.length === maxChunks) {
                  await this.requestQueue.put({ id: uuidv4(), totalSize, attachments })
                  totalSize = 0
                  attachments = []
               }

               if (mp4boxFile && (!state.videoMetadataExtracted || !state.subtitlesExtracted)) {
                  appendMp4BoxBuffer(mp4boxFile, chunk, offset)
               } else {
                  //todo flush... and unsetExtractionOptions
               }

               attachments.push({
                  "type": attachmentType.file,
                  "fileObj": queueFile.fileObj,
                  "rawBlob": chunk,
                  "fragmentSequence": chunkSequence + 1,
                  "offset": offset,
                  "crc": crc32buf(new Uint8Array(buf), 0)
               })


               totalSize += roundUpTo64(chunk.size)
               offset += chunk.size
               chunkSequence++

               state.setCrc(crc32buf(new Uint8Array(buf), state.crc))
               state.onNewFileChunk(offset, chunkSequence)


               // we have to yield
               if (totalSize >= maxChunkSize || attachments.length >= maxChunks - 1) {
                  await this.requestQueue.put({ id: uuidv4(), totalSize, attachments })
                  totalSize = 0
                  attachments = []
               }
            }

            state.setTotalChunks(chunkSequence)
            this.cleanMp4Box(frontendId)


         } catch (err) {
            if (err.name === "NotFoundError") {
               this.uploadRuntime.getFileState(frontendId).setStatus(fileUploadStatus.fileGoneInRequestProducer)
               this.goneFiles.push(queueFile)
            } else {
               console.error(err)
               this.uploadRuntime.getFileState(frontendId).setStatus(fileUploadStatus.errorOccurred)
               this.uploadRuntime.getFileState(frontendId).setError(err)
            }
         }
      }
      if (attachments.length > 0) {
         await this.requestQueue.put({ id: uuidv4(), totalSize, attachments })
      }
      this._running = false
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
      const frontendId = queueFile.fileObj.frontendId
      const state = this.uploadRuntime.getFileState(frontendId)
      if (queueFile.fileObj.size === 0) {
         state.markFileUploaded(frontendId)
         //todo
         let file = getUploader().discordResponseConsumer.getOrCreateState(queueFile.fileObj)
         getUploader().backendFileQueue.put(file)
         return true
      }
      return false
   }

   createAndPushSubtitleAttachment(frontendId, blob, subName, isForced) {
      const state = this.uploadRuntime.getFileState(frontendId)
      const fileObj = state.fileObj

      const attachment = { type: attachmentType.subtitle, fileObj, rawBlob: blob, subName, isForced }

      if (!this.subtitleAttachments.has(frontendId)) {
         this.subtitleAttachments.set(frontendId, [])
      }
      state.incrementExtractedSubtitleCount()
      this.subtitleAttachments.get(frontendId).push(attachment)
      this.tryEmitSubtitlesRequest(frontendId)
   }

   tryEmitSubtitlesRequest(frontendId) {
      const state = this.uploadRuntime.getFileState(frontendId)

      const expectedCount = state.expectedSubtitleCount
      const extractedCount = state.extractedSubtitleCount

      const attachments = this.subtitleAttachments.get(frontendId)
      console.log("expectedCount: " + expectedCount)
      console.log("extractedCount: " + extractedCount)
      console.log("attachments: " + attachments.length)
      if (!expectedCount || extractedCount !== expectedCount) {
         return
      }
      const maxAttachments = this.mainStore.user.maxAttachmentsPerMessage

      const batches = []
      for (let i = 0; i < attachments.length; i += maxAttachments) {
         batches.push(attachments.slice(i, i + maxAttachments))
      }

      state.markSubtitlesExtracted(frontendId)

      for (const batch of batches) {
         console.log("batch: " + JSON.stringify(batch))
         let totalSize = 0
         for (const att of batch) {
            totalSize += att.rawBlob.size
         }

         this.requestQueue.put({
            id: uuidv4(),
            totalSize,
            attachments: batch
         })
      }

      this.subtitleAttachments.delete(frontendId)
   }

   cleanMp4Box(frontendId) {
      let mp4boxFile = this.mp4Boxes.get(frontendId)
      if (mp4boxFile) {
         mp4boxFile.flush()
         this.mp4Boxes.delete(frontendId)
      }
   }

   makeUniqueSubName(base, id) {
      if (!base || base.trim() === "") {
         return "" + id
      }
      const count = this.subtitleNames.get(base) || 0
      this.subtitleNames.set(base, count + 1)

      if (count === 0) return base

      return `${base}-${id}`
   }

   getGoneFile(frontendId) {
      const index = this.goneFiles.findIndex(f => f.fileObj.frontendId === frontendId)
      if (index === -1) return
      const file = this.goneFiles[index]
      this.goneFiles.splice(index, 1)
      return file
   }
}
