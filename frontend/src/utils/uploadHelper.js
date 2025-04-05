import { useUploadStore } from "@/stores/uploadStore.js"
import { create } from "@/api/folder.js"
import { baseURL, encryptionMethod } from "@/utils/constants.js"
import jsmediatags from "jsmediatags"
import { uploadInstance } from "@/utils/networker.js"
import { useMainStore } from "@/stores/mainStore.js"

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

export function isAudioFile(file) {
   return file.fileObj.type.includes("audio/")
}


export function isVideoFile(file) {
   return file.fileObj.type.includes("video/")
}


let currentWebhookIndex = 0
export function getWebhook() {
   let uploadStore = useUploadStore()
   let webhooks = uploadStore.webhooks

   let webhook = webhooks[currentWebhookIndex]

   currentWebhookIndex = (currentWebhookIndex + 1) % webhooks.length

   return webhook
}


export async function getAudioCover(file) {
   return new Promise((resolve, reject) => {
      jsmediatags.read(file.systemFile, {
         onSuccess: (tag) => {
            let picture = tag.tags.picture
            if (picture) {
               let { data, format } = picture
               let byteArray = new Uint8Array(data)
               let blob = new Blob([byteArray], { type: format })
               resolve(blob)
            } else {
               reject(new Error("No picture found in audio file"))
            }
         },
         onError: (error) => {
            console.error("Error reading file:", error.type, error.info)
            reject(new Error("Failed to read audio file"))
         }
      })
   })
}


export function captureVideoFrame(videoPlayer, seekTo = 0, quality = 0.75, maxWidth = null, maxHeight = null) {
   return new Promise((resolve, reject) => {

      // Seek video after a short delay
      setTimeout(() => {
         videoPlayer.currentTime = seekTo
      }, 20)

      // Extract thumbnail when seeking is complete
      videoPlayer.addEventListener("seeked", () => {
         // Create canvas with video dimensions
         let canvas = document.createElement("canvas")

         // Draw video frame to canvas
         let ctx = canvas.getContext("2d")

         let width = videoPlayer.videoWidth
         let height = videoPlayer.videoHeight
         if (maxWidth && maxHeight) {
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
         }

         canvas.width = width
         canvas.height = height
         ctx.drawImage(videoPlayer, 0, 0, canvas.width, canvas.height)

         // Convert canvas to blob and resolve promise
         ctx.canvas.toBlob(
            (blob) => {
               resolve({
                  thumbnail: blob,
                  duration: videoPlayer.duration
               })
            },
            "image/jpeg",
            quality
         )
         videoPlayer.pause()
         URL.revokeObjectURL(videoPlayer.src)
      })
   })
}

export function parseVideoMetadata(info) {
   let videoMetadata = {}
   console.log(info)
   videoMetadata.video_tracks = []
   videoMetadata.audio_tracks = []
   videoMetadata.subtitle_tracks = []

   videoMetadata.is_progressive = info.isProgressive
   videoMetadata.is_fragmented = info.isFragmented
   videoMetadata.has_moov = info.hasMoov
   videoMetadata.has_IOD = info.hasIOD

   videoMetadata.mime = info.mime
   videoMetadata.brands = info.brands.join(', ')

   for (let infoTrack of info.tracks) {
      let track = {}
      track.bitrate = parseFloat((infoTrack.bitrate).toFixed(2))
      track.codec = infoTrack.codec
      track.size = infoTrack.size

      track.duration =  parseFloat((infoTrack.duration / infoTrack.timescale).toFixed(2))
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
   console.log(videoMetadata)
   return videoMetadata
}


export function getVideoCover(file, seekTo = -2, retryTimes = 0) {
   return new Promise((resolve, reject) => {
      let videoPlayer = document.createElement("video")
      videoPlayer.src = URL.createObjectURL(file.systemFile)

      videoPlayer.addEventListener("error", (ex) => {
         reject("Error when loading video file", ex)
      })

      videoPlayer.addEventListener("loadedmetadata", () => {
         captureVideoFrame(videoPlayer, seekTo)
            .then((result) => {
               const canvas = document.createElement("canvas")
               const ctx = canvas.getContext("2d")

               // Checking if the thumbnail is not pitch black
               ctx.canvas.width = ctx.canvas.height = 1
               ctx.drawImage(videoPlayer, 0, 0, 1, 1)
               let resultData = ctx.getImageData(0, 0, 1, 1)
               let totalColor = resultData.data[0] + resultData.data[1] + resultData.data[2] + resultData.data[3]

               if (totalColor === 255 && retryTimes <= 10) {
                  // Retry with a new timestamp if the thumbnail is pitch black
                  if (seekTo < 0) {
                     seekTo = 0
                  } else if (seekTo >= 0) {
                     seekTo += 2
                  }

                  if (seekTo > videoPlayer.duration) {
                     seekTo = videoPlayer.duration / 2
                  }

                  resolve(getVideoCover(file, seekTo, retryTimes + 1))
               } else {
                  resolve(result)
               }
            })
            .catch((error) => {
               reject(error)
            })
      })

      videoPlayer.load()
   })
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
   } else {
      throw Error(`unable to match encryptionMethod: ${method}`)
   }
   return ivToBase64(iv)


}


export function roundUpTo64(size) {
   return Math.ceil(size / 64) * 64
}


export function generateKey() {
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