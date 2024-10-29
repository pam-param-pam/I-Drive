import { useUploadStore } from "@/stores/uploadStore2.js"

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

   console.log("Scanned Files:")
   console.log(files)
   return files // Return the flat list of files with paths
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
         let fullPath = fileEntry.fullPath;
         console.log(fullPath)
         console.log(file.name)
         file.path = fullPath.startsWith("/") ? fullPath.slice(1) : fullPath;

         if (file.path === file.name) {
            file.path = ""
         }

         resolve(file);
      }, reject);
   });
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

   return videoMimeTypes.includes(file.type)
}

export function getVideoCover(file) {
   console.log("getting video cover for file: ", file)
   return new Promise((resolve, reject) => {
      // load the file to a video player
      let videoPlayer = document.createElement("video")
      videoPlayer.setAttribute("src", URL.createObjectURL(file))
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

export function getFileId(file) {
   let uploadStore = useUploadStore()

   // file = createdFiles[file.uploadId+file.path+file.name]
   return file
}

export function getOrCreateFolder(path) {

}

export function buildRequest(path) {

}