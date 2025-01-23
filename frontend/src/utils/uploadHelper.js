import { useUploadStore } from "@/stores/uploadStore.js"
import { create } from "@/api/folder.js"
import { encryptionMethod } from "@/utils/constants.js"
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

export function detectExtension(filename) {
   let arry = filename.split(".")

   if (arry.length === 1) return ".txt" //missing extension defaults to .txt
   return "." + arry[arry.length - 1]

}

export function detectType(fileObj) {
   let extension = detectExtension(fileObj.name)
   const RAW_IMAGE_EXTENSIONS = [
      ".IIQ", ".3FR", ".DCR", ".K25", ".KDC",
      ".CRW", ".CR2", ".CR3", ".ERF", ".MEF",
      ".MOS", ".NEF", ".NRW", ".ORF", ".PEF",
      ".RW2", ".ARW", ".SRF", ".SR2"
   ]
   if (RAW_IMAGE_EXTENSIONS.includes(extension.toUpperCase())) {
      return "image/raw"
   }

   return fileObj.type

}

export function isVideoFile(file) {
   // List of common video MIME types
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

export function getVideoCover(file, seekTo = -2) {
   console.log("getting video cover for file: ", file.fileObj.name)

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
         }, 100)

         // Extract thumbnail when seeking is complete
         videoPlayer.addEventListener("seeked", () => {
            console.log("Video is now paused at " + seekTo + "s.")

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
                  result = result.data[0] + result.data[1] + result.data[2] + result.data[3]
                  if (result === 255) {
                     resolve(getVideoCover(file, seekTo + 3))
                  } else {
                     resolve(blob)
                  }

               },
               "image/jpeg",
               0.75
            )


            videoPlayer.pause()
            URL.revokeObjectURL(videoPlayer.src)
            console.log("FINISHED GETTING COVER")
         })

      })

      videoPlayer.load()
   })
}

export function getFileId(fileObj) {
   let uploadStore = useUploadStore()
   return uploadStore.createdFiles[fileObj.frontendId]

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
      let path_key = pathParts.slice(0, i).join("/")
      if (uploadStore.createdFolders[path_key]) {
         parentFolder = uploadStore.createdFolders[path_key]
      } else {
         let folderName = pathParts.slice(0, i)[pathParts.slice(0, i).length - 1]

         let folder = await create({ "parent_id": parentFolder, "name": folderName })
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

export function generateThumbnailIv(fileObj) {
   if (fileObj.encryptionMethod === encryptionMethod.AesCtr) {
      let iv = crypto.getRandomValues(new Uint8Array(16))
      return ivToBase64(iv)
   }
   if (fileObj.encryptionMethod === encryptionMethod.ChaCha20) {
      let iv = crypto.getRandomValues(new Uint8Array(12))
      return ivToBase64(iv)

   }

}
