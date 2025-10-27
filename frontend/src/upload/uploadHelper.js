import { useUploadStore } from "@/stores/uploadStore.js"
import { encryptionMethod, fileUploadStatus } from "@/utils/constants.js"
import jsmediatags from "jsmediatags"
import { uploadInstance } from "@/axios/networker.js"
import { showToast } from "@/utils/common.js"

const worker = new Worker(new URL("../workers/encryptorWorker.js", import.meta.url), { type: "module" })


export async function checkFilesSizes(files) {
   let smallFileCount = 0
   let threshold = 100
   let maxFileSize = 0.5 * 1024 * 1024 // 0.5 MB in bytes

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

   if (!webhooks || webhooks.length === 0) return null

   // Count webhooks per channel
   const channelCounts = {}
   webhooks.forEach(wh => {
      const id = wh.channel.id
      channelCounts[id] = (channelCounts[id] || 0) + 1
   })

   // Build a flat weighted array: more weight for channels with fewer webhooks
   const weightedWebhooks = []
   webhooks.forEach(wh => {
      const weight = 1 / channelCounts[wh.channel.id]
      const times = Math.ceil(weight * 100) // scale to integer
      for (let i = 0; i < times; i++) weightedWebhooks.push(wh)
   })

   // Pick a random webhook from the weighted array
   return weightedWebhooks[Math.floor(Math.random() * weightedWebhooks.length)]
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
         let data = await getVideoCover(queueFile)
         let duration = data.duration
         thumbnail = data.thumbnail
         queueFile.fileObj.duration = Math.round(duration)

      } catch (e) {
         console.warn(e)
         showToast("error", "Couldn't get thumbnail for: " + queueFile.fileObj.name)
      }
   }
   //generating a thumbnail for an image
   if (isImageFile(queueFile.fileObj.extension)) {
      try {
         thumbnail = await getImageThumbnail(queueFile)
      } catch (e) {
         console.warn(e)
         showToast("error", "Couldn't get thumbnail for: " + queueFile.fileObj.name)
      }
   }
   return thumbnail
}


export function getVideoCover(file, seekTo = -2, retryTimes = 0) {
   return new Promise((resolve, reject) => {
      const videoPlayer = document.createElement("video")
      videoPlayer.src = URL.createObjectURL(file.systemFile)

      videoPlayer.addEventListener("error", () => {
         reject(new Error("Error when loading video file"))
      })

      videoPlayer.addEventListener("loadedmetadata", () => {
         captureVideoFrame(videoPlayer, seekTo, true)
            .then((frames) => {
               if (frames.length === 1) {
                  if (isPitchBlack(frames[0].canvas) && retryTimes < 5) {
                     resolve(getVideoCover(file, seekTo + 2, retryTimes + 1))
                  }
               }
               createThumbnails(frames)
                  .then((thumbnails) => {
                     const largestThumbnail = findLargestThumbnail(thumbnails)
                     resolve({
                        thumbnail: largestThumbnail,
                        duration: frames[0].duration
                     })
                  })
                  .catch(reject)
            })
            .catch(reject)
      })

      videoPlayer.load()
   })
}


function createThumbnails(frames) {
   const thumbnailPromises = frames.map(frame => createThumbnail(frame.canvas))
   return Promise.all(thumbnailPromises)
}


function findLargestThumbnail(thumbnails) {
   thumbnails.sort((a, b) => b.size - a.size)
   return thumbnails[0]
}


function isPitchBlack(canvas) {
   const testCanvas = document.createElement("canvas")
   testCanvas.width = testCanvas.height = 1
   const tinyCtx = testCanvas.getContext("2d")
   tinyCtx.drawImage(canvas, 0, 0, 1, 1)

   const data = tinyCtx.getImageData(0, 0, 1, 1).data
   const totalColor = data[0] + data[1] + data[2] + data[3]

   return totalColor === 255
}


function createThumbnail(source, options = {}) {
   const {
      quality = 0.65,
      maxWidth = 1280,
      maxHeight = 720,
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


export function captureVideoFrame(videoPlayer, seekTo, multiple, options = {}) {
   return new Promise((resolve, reject) => {
      const width = videoPlayer.videoWidth
      const height = videoPlayer.videoHeight
      const frames = []

      const captureAndCheckThumbnail = (seekPosition, attempt) => {
         videoPlayer.currentTime = seekPosition

         videoPlayer.addEventListener("seeked", () => {
            const frameCanvas = document.createElement("canvas")
            frameCanvas.width = width
            frameCanvas.height = height
            const ctx = frameCanvas.getContext("2d")
            ctx.drawImage(videoPlayer, 0, 0, width, height)

            frameCanvas.toBlob(blob => {
               if (!blob) {
                  reject(new Error(`Failed to create Blob from canvas at seek position ${seekPosition}`))
                  return
               }

               frames.push({
                  thumbnail: blob,
                  canvas: frameCanvas,
                  duration: videoPlayer.duration,
                  seekPosition: seekPosition
               })

               if (attempt < (multiple ? 5 : 1) - 1) {
                  const nextSeekPosition = seekPosition + (videoPlayer.duration * 0.1)
                  captureAndCheckThumbnail(nextSeekPosition, attempt + 1)
               } else {
                  resolve(frames)
               }
            }, options.type, options.quality)

         }, { once: true })

         videoPlayer.currentTime = seekPosition
      }

      captureAndCheckThumbnail(seekTo, 0)
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
      status === fileUploadStatus.fileGone
}


// export async function encryptAttachment(attachment) {
//    let fileObj = attachment.fileObj
//    let bytesToSkip = 0
//    if (attachment.type === attachmentType.file) {
//       bytesToSkip = attachment.offset
//    }
//    let iv = fileObj.iv
//    let key = fileObj.key
//
//    if (attachment.type === attachmentType.thumbnail) {
//       iv = attachment.iv
//       key = attachment.key
//    }
//    return await encryptInWorker(attachment.rawBlob, fileObj.encryptionMethod, key, iv, bytesToSkip)
// }

export async function encryptInWorker(rawBlob, method, key, iv, bytesToSkip) {
   return new Promise((resolve, reject) => {
      worker.onmessage = (e) => {
         if (e.data.error) return reject(e.data.error)
         resolve(e.data.encryptedBlob)
      }
      worker.onerror = (err) => {
         reject(err)
      }
      worker.postMessage({ rawBlob, method, key, iv, bytesToSkip })
   })
}