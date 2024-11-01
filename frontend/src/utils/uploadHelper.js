import { useUploadStore } from "@/stores/uploadStore.js"
import { create } from "@/api/folder.js"
import { encryptionMethod } from "@/utils/constants.js"

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
         file.path = fullPath.startsWith("/") ? fullPath.slice(1) : fullPath

         if (file.path === file.name) {
            file.path = ""
         }

         resolve(file)
      }, reject)
   })
}

export function detectExtension(filename) {
   let arry = filename.split(".")

   if (arry.length === 1) return ".txt" //missing extension defaults to .txt
   return "." + arry[arry.length - 1]

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

export function getVideoCover(file) {
   console.log("getting video cover for file: ", file.fileObj.name)
   return new Promise((resolve, reject) => {
      // load the file to a video player
      let videoPlayer = document.createElement("video")
      videoPlayer.setAttribute("src", URL.createObjectURL(file.systemFile))
      videoPlayer.load()
      videoPlayer.addEventListener("error", (ex) => {
         reject("error when loading video file", ex)
      })
      // load metadata of the video to get video duration and dimensions
      videoPlayer.addEventListener("loadedmetadata", () => {

         let seekTo
         // seek to defined timestamp (in seconds) if possible
         if (videoPlayer.duration >= 30) {
            seekTo = 30
         } else if (videoPlayer.duration >= 20) {
            seekTo = 20
         } else if (videoPlayer.duration >= 10) {
            seekTo = 10
         } else if (videoPlayer.duration >= 5) {
            seekTo = 5
         } else {
            seekTo = 0
         }

         // delay seeking or else 'seeked' event won't fire on Safari
         setTimeout(() => {
            videoPlayer.currentTime = seekTo
         }, 200)
         // extract video thumbnail once seeking is complete
         videoPlayer.addEventListener("seeked", () => {
            console.log("video is now paused at %ss.", seekTo)
            // define a canvas to have the same dimension as the video
            const canvas = document.createElement("canvas")
            canvas.width = videoPlayer.videoWidth
            canvas.height = videoPlayer.videoHeight
            // draw the video frame to canvas
            const ctx = canvas.getContext("2d")
            ctx.drawImage(videoPlayer, 0, 0, canvas.width, canvas.height)
            // return the canvas image as a blob
            ctx.canvas.toBlob(
               blob => {
                  resolve(blob)
               },
               "image/jpeg",
               0.75
            )
         })
      })
      URL.revokeObjectURL(file)  // Free memory once done

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
      }
      else {
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
   let binary = '';
   iv.forEach((byte) => binary += String.fromCharCode(byte));

   // Then, encode the binary string in Base64
   return btoa(binary);
}
export function generateThumbnailIv(fileObj) {
   if (fileObj.encryptionMethod === encryptionMethod.AesCtr) {
      let iv = crypto.getRandomValues(new Uint8Array(16))
      return ivToBase64(iv)
   }
   if (fileObj.encryptionMethod === encryptionMethod.ChaCha20) {
      let iv =  crypto.getRandomValues(new Uint8Array(12))
      return ivToBase64(iv)

   }

}