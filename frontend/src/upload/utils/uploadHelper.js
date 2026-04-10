import { useUploadStore } from "@/stores/uploadStore.js"
import { encryptionMethod, fileUploadStatus } from "@/utils/constants.js"
import { uploadInstance } from "@/axios/networker.js"
import { detectExtension, showToast } from "@/utils/common.js"
import {
   fastVideoThumbnail,
   generateAudioThumbnail,
   generateImageThumbnail,
   generateRawImageThumbnail,
   slowVideoCover
} from "@/upload/utils/thumbnailHelper.js"
import { useMainStore } from "@/stores/mainStore.js"


export async function checkFilesSizes(files) {
   let smallFileCount = 0
   let threshold = 100
   let maxFileSize = 0.5 * 1024 * 1024

   for (let file of files) {
      let size = file.file?.size || file.size
      if (size < maxFileSize) {
         smallFileCount++
         if (smallFileCount > threshold) {
            return true
         }
      }
   }
   return false
}


export async function scanDataTransfer(dataTransfer) {
   let files = []
   let items = dataTransfer.items

   // Queue to hold items for processing, allowing files and directories to be handled consistently
   let queue = []

   // Collect initial items into the queue
   for (let i = 0; i < items.length; i++) {
      let item = items[i].webkitGetAsEntry()
      if (item) queue.push(item)
   }

   // Process each item in the queue
   while (queue.length > 0) {
      let item = queue.shift() // Get the next item in the queue

      if (item.isFile) {
         // Process and add the file
         files.push(await processFile(item))
      } else if (item.isDirectory) {
         // Process directory and add its contents to the queue
         let directoryFiles = await processDirectory(item)
         files = files.concat(directoryFiles)
      }
   }

   return files
}


// Recursively process directories and collect files with their full paths
async function processDirectory(directoryEntry) {
   let files = []
   const reader = directoryEntry.createReader()


   async function readAllEntries() {
      let batch = await new Promise((resolve, reject) => {
         reader.readEntries(resolve, reject)
      })

      while (batch.length) {
         for (const entry of batch) {
            if (entry.isFile) {
               files.push(await processFile(entry))
            } else if (entry.isDirectory) {
               files.push(...await processDirectory(entry))
            }
         }

         batch = await new Promise((resolve, reject) => {
            reader.readEntries(resolve, reject)
         })
      }
   }


   await readAllEntries()
   return files
}


function processFile(fileEntry) {
   return new Promise((resolve, reject) => {
      fileEntry.file(function(file) {
         // Check if the file is in a directory by looking for a "/"
         let fullPath = fileEntry.fullPath
         let path = fullPath.startsWith("/") ? fullPath.slice(1) : fullPath

         if (path === file.name) {
            path = ""
         }

         resolve({ file, path })
      }, reject)
   })
}


export function isAudioFile(extension) {
   extension = extension.toLowerCase()
   let uploadStore = useUploadStore()
   return uploadStore.fileExtensions.Audio.includes(extension)
}


export function isVideoFile(extension) {
   extension = extension.toLowerCase()
   let uploadStore = useUploadStore()
   return uploadStore.fileExtensions.Video.includes(extension)
}

export function isZipFile(extension) {
   extension = extension.toLowerCase()
   return extension === ".zip"
}

export function isImageFile(extension) {
   extension = extension.toLowerCase()
   let uploadStore = useUploadStore()
   return uploadStore.fileExtensions.Image.includes(extension)
}


export function isRawImageFile(extension) {
   extension = extension.toLowerCase()
   let uploadStore = useUploadStore()
   return uploadStore.fileExtensions["Raw image"].includes(extension)
}


let webhookIndex = 0


export function getWebhook() {
   const uploadStore = useUploadStore()
   const webhooks = uploadStore.webhooks

   if (!webhooks || webhooks.length === 0) return null

   const webhook = webhooks[webhookIndex % webhooks.length]
   webhookIndex++

   return webhook
}


export async function makeThumbnailIfNeeded(queueFile) {
   let thumbnail = null
   let other = {}
   try {
      //extracting thumbnail if needed for audio file
      if (isAudioFile(queueFile.fileObj.extension)) {
         thumbnail = await generateAudioThumbnail(queueFile.systemFile)
      }
      //generating a thumbnail if needed for video file
      if (isVideoFile(queueFile.fileObj.extension)) {
         if (queueFile.fileObj.size > 300 * 1024 * 1024) {
            thumbnail = await slowVideoCover(queueFile.systemFile)
         }
         thumbnail = await fastVideoThumbnail(queueFile.systemFile)
      }
      //generating a thumbnail for an image
      if (isImageFile(queueFile.fileObj.extension)) {
         let data = await generateImageThumbnail(queueFile.systemFile)
         thumbnail = data.thumbnail
         other.photoMetadata = data.photoMetadata
      }

      //generating a thumbnail for a raw image
      if (isRawImageFile(queueFile.fileObj.extension)) {
         let data = await generateRawImageThumbnail(queueFile.systemFile)
         thumbnail = data.thumbnail
         other.rawMetadata = parseRawMetadata(data.metadata)
      }
   } catch (e) {
      console.warn(e)
      showToast("error", "Couldn't get thumbnail for: " + queueFile.fileObj.name)
   }
   return { thumbnail, other }

}


export function parseRawMetadata(text) {
   const lines = text.split("\n")

   const map = {}

   for (const line of lines) {
      const idx = line.indexOf(":")
      if (idx === -1) continue

      const key = line.slice(0, idx).trim()
      map[key] = line.slice(idx + 1).trim()
   }
   let owner = map["Owner"]
   if (!owner || owner === "unknown") owner = null
   return {
      camera: map["Camera"] || null,
      camera_owner: owner,
      iso: map["ISO speed"] || null,
      shutter: map["Shutter"] || null,
      aperture: map["Aperture"] || null,
      focal_length: map["Focal length"] || null,
      lens_model: map["Focal length"] || null
   }
}


export function parseVideoMetadata(info) {
   let videoMetadata = {}
   videoMetadata.video_tracks = []
   videoMetadata.audio_tracks = []
   videoMetadata.subtitle_tracks = []

   videoMetadata.is_progressive = info.isProgressive
   videoMetadata.is_fragmented = info.isFragmented
   videoMetadata.has_moov = info.hasMoov
   videoMetadata.has_IOD = info.hasIOD

   videoMetadata.mime = cleanCodecString(info.mime)
   videoMetadata.brands = info.brands.join(", ")

   for (let infoTrack of info.tracks) {
      let track = {}
      track.bitrate = parseFloat((infoTrack.bitrate).toFixed(2))
      track.codec = infoTrack.codec
      track.size = infoTrack.size

      track.duration = parseFloat((infoTrack.duration / infoTrack.timescale).toFixed(2))
      track.language = infoTrack.language === "und" ? null : infoTrack.language

      let trackType = infoTrack.type
      if (trackType === "video") {
         track.height = infoTrack.video.height
         track.width = infoTrack.video.width
         track.fps = Math.round(infoTrack.timescale * infoTrack.nb_samples / infoTrack.samples_duration)
         track.track_number = videoMetadata.video_tracks.length + 1
         videoMetadata.video_tracks.push(track)

      } else if (trackType === "audio") {
         track.name = infoTrack.name
         track.channel_count = infoTrack.audio.channel_count
         track.sample_rate = infoTrack.audio.sample_rate
         track.sample_size = infoTrack.audio.sample_size
         track.track_number = videoMetadata.audio_tracks.length + 1
         videoMetadata.audio_tracks.push(track)

      } else if (trackType === "subtitles") {
         track.name = infoTrack.name
         track.track_number = videoMetadata.subtitle_tracks.length + 1
         videoMetadata.subtitle_tracks.push(track)
      }
   }
   return videoMetadata
}


export function appendMp4BoxBuffer(mp4box, chunk, offset) {
   chunk.arrayBuffer(offset)
      .then((buffer) => {
         buffer.fileStart = offset
         mp4box.appendBuffer(buffer)
      })
}


export function ivToBase64(iv) {
   // First, convert the Uint8Array to a regular binary string
   let binary = ""
   iv.forEach((byte) => binary += String.fromCharCode(byte))

   // Then, encode the binary string in Base64
   return btoa(binary)
}


export function generateIv(method) {
   let iv
   if (method === encryptionMethod.AesCtr) {
      iv = crypto.getRandomValues(new Uint8Array(16))
   } else if (method === encryptionMethod.ChaCha20) {
      iv = crypto.getRandomValues(new Uint8Array(12))
   } else if (method === encryptionMethod.NotEncrypted) {
      return null
   } else {
      throw Error(`unable to match encryptionMethod: ${method}`)
   }
   return ivToBase64(iv)
}


export function roundUpTo64(size) {
   return Math.ceil(size / 64) * 64
}


export function generateKey(method) {
   if (method === encryptionMethod.NotEncrypted) {
      return null
   }
   let key = crypto.getRandomValues(new Uint8Array(32))
   return ivToBase64(key)
}


export async function upload(formData, config) {
   let headers = {}
   let webhook = getWebhook()

   config.headers = {
      ...config.headers,
      ...headers
   }
   config.__webhook = webhook
   return await uploadInstance.post(webhook.url, formData, config)
}


export function isErrorStatus(status) {
   return status === fileUploadStatus.errorOccurred ||
      status === fileUploadStatus.uploadFailed ||
      status === fileUploadStatus.saveFailed ||
      status === fileUploadStatus.fileGoneInUpload ||
      status === fileUploadStatus.fileGoneInRequestProducer
}


export function getFileType(fileName) {
   let mainStore = useMainStore()

   let ext = detectExtension(fileName)

   return mainStore.config.extensions?.[ext] || "Other"
}

function cleanCodecString(input) {
   const codecsMatch = input.match(/codecs="([^"]+)"/)
   if (!codecsMatch) return input

   const rawCodecs = codecsMatch[1]
      .split(",")
      .map(c => c.trim())
      .filter(Boolean)

   const uniqueCodecs = [...new Set(rawCodecs)]

   const cleaned = input
      .replace(/profiles="[^"]*"/, "")
      .replace(/\s{2,}/g, " ")
      .trim()

   return cleaned.replace(
      /codecs="[^"]*"/,
      `codecs="${uniqueCodecs.join(", ")}"`
   ).replace(/\s*;+\s*$/, "")
}