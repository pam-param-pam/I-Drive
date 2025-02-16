import { useUploadStore } from "@/stores/uploadStore.js"
import { create } from "@/api/folder.js"
import { encryptionMethod } from "@/utils/constants.js"
import jsmediatags from "jsmediatags"

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


export function detectType(fileObj) {
   const RAW_IMAGE_EXTENSIONS = [
      ".IIQ", ".3FR", ".DCR", ".K25", ".KDC",
      ".CRW", ".CR2", ".CR3", ".ERF", ".MEF",
      ".MOS", ".NEF", ".NRW", ".ORF", ".PEF",
      ".RW2", ".ARW", ".SRF", ".SR2"
   ]
   if (RAW_IMAGE_EXTENSIONS.includes(fileObj.extension.toUpperCase())) {
      return "image/raw"
   }
   if (fileObj.extension === ".mov") {
      return "video/mov"
   }
   if (fileObj.extension === ".mod") {
      return "text/plain"
   }
   return fileObj.type

}

export function isAudioFile(file) {
   return file.fileObj.type.includes("audio/")
}

export function isVideoFile(file) {
   if (file.fileObj.extension === ".mov") return true
   const videoMimeTypes = [
      "video/mp4",
      "video/mpeg",
      "video/ogg",
      "video/webm",
      "video/quicktime",
      "video/x-msvideo",
      "video/x-ms-wmv",
      "video/x-flv",
      "video/3gpp",
      "video/3gpp2"
   ]

   return videoMimeTypes.includes(file.fileObj.type)
}

export function getWebhook(currentWebhook) {
   const uploadStore = useUploadStore()

   let webhooks = uploadStore.webhooks
   let currentWebhookIndex = webhooks.findIndex(webhook => webhook.discord_id === currentWebhook.discord_id)
   currentWebhookIndex = (currentWebhookIndex + 1) % webhooks.length

   return webhooks[currentWebhookIndex]
}

export async function getAudioCover(file) {
   return new Promise((resolve, reject) => {
      jsmediatags.read(file.systemFile, {
         onSuccess: (tag) => {
            const picture = tag.tags.picture
            if (picture) {
               const { data, format } = picture
               const byteArray = new Uint8Array(data)
               const blob = new Blob([byteArray], { type: format })
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


export function getVideoCover(file, seekTo = -2, retryTimes = 0) {
   return new Promise((resolve, reject) => {
      let videoPlayer = document.createElement("video")
      videoPlayer.src = URL.createObjectURL(file.systemFile)

      // Error handling
      videoPlayer.addEventListener("error", (ex) => {
         reject("Error when loading video file", ex)
      })

      // Load metadata and get video thumbnail
      videoPlayer.addEventListener("loadedmetadata", () => {

         // Seek video after a short delay
         setTimeout(() => {
            videoPlayer.currentTime = seekTo
         }, 20)

         // Extract thumbnail when seeking is complete
         videoPlayer.addEventListener("seeked", () => {

            // Create canvas with video dimensions
            const canvas = document.createElement("canvas")
            canvas.width = videoPlayer.videoWidth
            canvas.height = videoPlayer.videoHeight

            // Draw video frame to canvas
            const ctx = canvas.getContext("2d")
            ctx.drawImage(videoPlayer, 0, 0, canvas.width, canvas.height)

            // Convert canvas to blob and resolve promise
            ctx.canvas.toBlob(
               (blob) => {
                  // checking if the thumbnail is not pitch black
                  ctx.canvas.width = ctx.canvas.height = 1
                  ctx.drawImage(videoPlayer, 0, 0, 1, 1)
                  let result = ctx.getImageData(0, 0, 1, 1)
                  let totalColor = result.data[0] + result.data[1] + result.data[2] + result.data[3]
                  if (totalColor === 255 && retryTimes <= 10) {
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
                     resolve({
                        thumbnail: blob,
                        duration: videoPlayer.duration
                     })
                  }

               },
               "image/jpeg",
               0.75
            )


            videoPlayer.pause()
            URL.revokeObjectURL(videoPlayer.src)
         })

      })

      videoPlayer.load()
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

export function generateIv(fileObj) {
   let iv
   if (fileObj.encryptionMethod === encryptionMethod.AesCtr) {
      iv = crypto.getRandomValues(new Uint8Array(16))
   } else if (fileObj.encryptionMethod === encryptionMethod.ChaCha20) {
      iv = crypto.getRandomValues(new Uint8Array(12))
   } else {
      throw Error("unable to match encryptionMethod")
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