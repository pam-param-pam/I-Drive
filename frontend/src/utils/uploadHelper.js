import { useUploadStore } from "@/stores/uploadStore.js"
import { create } from "@/api/folder.js"
import { baseURL, encryptionMethod } from "@/utils/constants.js"
import jsmediatags from "jsmediatags"
import { uploadInstance } from "@/utils/networker.js"
import { useMainStore } from "@/stores/mainStore.js"
import { useToast } from "vue-toastification"

const toast = useToast()


export async function checkFilesSizes(files) {
   let smallFileCount = 0
   let threshold = 100
   let maxFileSize = 0.5 * 1024 * 1024 // 0.5 MB in bytes

   for (let file of files) {
      if (file.size < maxFileSize) {
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

   // Create a reader to go through the directory's entries
   let reader = directoryEntry.createReader()

   // Use the reader to read entries in the directory (files and subdirectories)
   const readEntries = () =>
      new Promise((resolve, reject) => {
         reader.readEntries((entries) => {
            resolve(entries)
         }, reject)
      })
   let entries = await readEntries()

   // Iterate over each entry in the directory
   for (let entry of entries) {
      // Construct the new path for each entry

      if (entry.isFile) {
         // Process and add the file with its full path
         files.push(await processFile(entry))
      } else if (entry.isDirectory) {
         // Recursively process subdirectory and add its files
         files.push(...await processDirectory(entry))
      }
   }

   return files // Return all files with their full paths
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
   return uploadStore.fileExtensions.audio.includes(extension)
}


export function isVideoFile(extension) {
   extension = extension.toLowerCase()
   let uploadStore = useUploadStore()
   return uploadStore.fileExtensions.video.includes(extension)
}


export function isImageFile(extension) {
   extension = extension.toLowerCase()
   let uploadStore = useUploadStore()
   return uploadStore.fileExtensions.image.includes(extension)
}


//todo yea this needs fixing lol
export function getWebhook() {
   const uploadStore = useUploadStore()
   const webhooks = uploadStore.webhooks

   // Step 1: Group webhooks by channel ID
   const channelMap = new Map()
   webhooks.forEach((wh) => {
      const channelId = wh.channel.id
      if (!channelMap.has(channelId)) {
         channelMap.set(channelId, [])
      }
      channelMap.get(channelId).push(wh)
   })

   // Step 2: Assign weights to each channel
   const weightedChannels = []
   for (const [channelId, hooks] of channelMap.entries()) {
      const weight = 1 / hooks.length // Fewer webhooks = higher weight
      weightedChannels.push({ channelId, webhooks: hooks, weight })
   }

   // Step 3: Weighted random selection of a channel
   const totalWeight = weightedChannels.reduce((sum, ch) => sum + ch.weight, 0)
   let r = Math.random() * totalWeight
   for (let i = 0; i < weightedChannels.length; i++) {
      r -= weightedChannels[i].weight
      if (r <= 0) {
         const hooks = weightedChannels[i].webhooks
         return hooks[Math.floor(Math.random() * hooks.length)]
      }
   }

   // Fallback
   const last = weightedChannels[weightedChannels.length - 1]
   return last.webhooks[Math.floor(Math.random() * last.webhooks.length)]
}


export async function makeThumbnailIfNeeded(queueFile) {
   let thumbnail
   //extracting thumbnail if needed for audio file
   if (isAudioFile(queueFile.fileObj.extension)) {
      try {
         thumbnail = await getAudioCover(queueFile)
      } catch (e) {
         console.warn(e)
      }
   }
   //generating a thumbnail if needed for video file
   if (isVideoFile(queueFile.fileObj.extension)) {
      try {
         console.log("getting video cover:")
         let data = await getVideoCover(queueFile)
         let duration = data.duration
         thumbnail = data.thumbnail
         queueFile.fileObj.duration = Math.round(duration)
         console.log("finnished getting video cover")

      } catch (e) {
         console.warn(e)
         toast.error("Couldn't get thumbnail for: " + queueFile.fileObj.name)
      }
   }
   //generating a thumbnail if needed for video file
   if (isImageFile(queueFile.fileObj.extension)) { // && queueFile.fileObj.size > 200 * 1024
      try {
         thumbnail = await getImageThumbnail(queueFile)
      } catch (e) {
         console.warn(e)
         toast.error("Couldn't get thumbnail for: " + queueFile.fileObj.name)
      }
   }
   return thumbnail
}


function createThumbnail(source, options = {}) {
   const {
      quality = 0.65,
      maxWidth = 1920,
      maxHeight = 1080,
      mimeType = "image/webp"
   } = options

   return new Promise((resolve) => {
      let width = source.width
      let height = source.height

      // Downscale to target resolution
      if (width > height) {
         if (width > maxWidth) {
            height *= maxWidth / width
            width = maxWidth
         }
      } else {
         if (height > maxHeight) {
            width *= maxHeight / height
            height = maxHeight
         }
      }

      // Draw downscaled image
      const canvas = document.createElement("canvas")
      canvas.width = Math.round(width)
      canvas.height = Math.round(height)

      const ctx = canvas.getContext("2d")
      ctx.drawImage(source, 0, 0, canvas.width, canvas.height)

      // Compress
      canvas.toBlob((blob) => {
         resolve(blob)
      }, mimeType, quality)
   })
}


export function getImageThumbnail(file, options = {}) {
   const defaultOptions = {
      quality: 0.5,
      ...options
   }
   return new Promise((resolve, reject) => {
      const img = new Image()

      img.onload = () => {
         createThumbnail(img, defaultOptions)
            .then(resolve)
            .catch(reject)
         URL.revokeObjectURL(img.src)
      }

      img.onerror = () => {
         reject(new Error("Failed to load image"))
      }

      img.src = URL.createObjectURL(file.systemFile)
   })
}


export async function getAudioCover(file, options = {}) {
   return new Promise((resolve, reject) => {
      jsmediatags.read(file.systemFile, {
         onSuccess: (tag) => {
            const picture = tag.tags.picture
            if (!picture) return reject(new Error("No picture found in audio file"))

            const { data, format } = picture
            const byteArray = new Uint8Array(data)
            const blob = new Blob([byteArray], { type: format })

            const img = new Image()
            img.onload = () => {
               createThumbnail(img, options).then(resolve).catch(reject)
               URL.revokeObjectURL(img.src)
            }
            img.onerror = reject
            img.src = URL.createObjectURL(blob)
         },
         onError: (error) => {
            console.error("Error reading file:", error.type, error.info)
            reject(new Error("Failed to read audio file"))
         }
      })
   })
}


export function captureVideoFrame(videoPlayer, seekTo = 0, options = {}) {
   return new Promise((resolve, reject) => {
      setTimeout(() => {
         videoPlayer.currentTime = seekTo
      }, 20)

      videoPlayer.addEventListener("seeked", () => {
         // Draw current video frame on canvas first
         const width = videoPlayer.videoWidth
         const height = videoPlayer.videoHeight

         const frameCanvas = document.createElement("canvas")
         frameCanvas.width = width
         frameCanvas.height = height
         const ctx = frameCanvas.getContext("2d")
         ctx.drawImage(videoPlayer, 0, 0, width, height)

         // Pass canvas to createThumbnail for resizing/compression
         createThumbnail(frameCanvas, options).then(blob => {
            resolve({
               thumbnail: blob,
               canvas: frameCanvas,
               duration: videoPlayer.duration
            })
         }).catch(reject)

         videoPlayer.pause()
         URL.revokeObjectURL(videoPlayer.src)
      }, { once: true })
   })
}


export function getVideoCover(file, seekTo = -2, retryTimes = 0) {
   return new Promise((resolve, reject) => {
      const videoPlayer = document.createElement("video")
      videoPlayer.src = URL.createObjectURL(file.systemFile)

      videoPlayer.addEventListener("error", () => {
         reject(new Error("Error when loading video file"))
      })

      videoPlayer.addEventListener("loadedmetadata", () => {
         captureVideoFrame(videoPlayer, seekTo)
            .then((result) => {
               // Downscale to 1x1 and check brightness
               const testCanvas = document.createElement("canvas")
               testCanvas.width = testCanvas.height = 1
               const tinyCtx = testCanvas.getContext("2d")
               tinyCtx.drawImage(result.canvas, 0, 0, 1, 1)

               const data = tinyCtx.getImageData(0, 0, 1, 1).data
               const totalColor = data[0] + data[1] + data[2] + data[3]

               if (totalColor === 255 && retryTimes <= 10) {
                  let nextSeek = seekTo < 0 ? 0 : seekTo + 2
                  if (nextSeek > videoPlayer.duration) {
                     nextSeek = videoPlayer.duration / 2
                  }
                  resolve(getVideoCover(file, nextSeek, retryTimes + 1))
               } else {
                  resolve({
                     thumbnail: result.thumbnail,
                     duration: result.duration
                  })
               }
            })
            .catch(reject)
      })

      videoPlayer.load()
   })
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

   videoMetadata.mime = info.mime
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


export async function getOrCreateFolder(fileObj) {
   let uploadStore = useUploadStore()
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
      if (uploadStore.createdFolders[path_key]) {
         parentFolder = uploadStore.createdFolders[path_key]
      } else {
         let folderName = pathParts.slice(0, i)[pathParts.slice(0, i).length - 1]

         let folder = await create({ "parent_id": parentFolder, "name": folderName }, {
            __retry500: true
         })
         parentFolder = folder.id
         uploadStore.createdFolders[path_key] = folder.id
      }
   }
   return parentFolder
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
   let mainStore = useMainStore()

   let url
   let headers = {}
   if (mainStore.settings.useProxy) {
      url = baseURL + "/proxy/discord"
      let token = localStorage.getItem("token")
      headers["Authorization"] = `Token ${token}`

   } else {
      url = getWebhook().url

   }
   config.headers = {
      ...config.headers,
      ...headers
   }
   return await uploadInstance.post(url, formData, config)
}