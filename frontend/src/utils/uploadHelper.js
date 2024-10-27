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

export async function scanFiles(dataTransfer) {
   let files = [];

   console.log("dataTransfer.files");

   console.log(dataTransfer.files);
   files.push(...dataTransfer.files)

   console.log(dataTransfer);
   let directories = dataTransfer.items;

   for (let i = 0; i < directories.length; i++) {
      let item = directories[i].webkitGetAsEntry(); // Get the entry (file or folder)

      if (item) {
         if (item.isFile) {
            // Process and add the file with its flat path
            files.push(await processFile(item, ""));
         } else if (item.isDirectory) {
            // Process directory and add files recursively with flat paths
            files = files.concat(await processDirectory(item, ""));
         }
      }
   }

   console.log("Scanned Files:");
   console.log(files);
   return files; // Return the flat list of files with paths
}

// Process individual file (returns a Promise to read the file and add flat path)
function processFile(fileEntry, path) {
   return new Promise((resolve, reject) => {
      fileEntry.file(function(file) {
         // Return both the file and its flat relative path
         const filePath = path ? `${path}/${fileEntry.name}` : fileEntry.name; // No leading slash for root level
         resolve({ file, path: filePath });
      }, reject);
   });
}

// Process directory (recursively read contents and return all files with flat paths)
function processDirectory(directoryEntry, parentPath) {
   return new Promise((resolve, reject) => {
      let reader = directoryEntry.createReader();
      let files = [];
      let currentPath = parentPath ? `${parentPath}/${directoryEntry.name}` : directoryEntry.name; // No leading slash for root level

      // Keep reading until all entries are processed
      function readEntries() {
         reader.readEntries(async function(entries) {
            if (entries.length === 0) {
               resolve(files); // Resolve when no more entries
               return;
            }

            for (let entry of entries) {
               if (entry.isFile) {
                  // Push each file with its flat path directly
                  files.push(await processFile(entry, currentPath));
               } else if (entry.isDirectory) {
                  // Recursively process folder and flatten the files list
                  const dirFiles = await processDirectory(entry, currentPath);
                  files = files.concat(dirFiles);
               }
            }

            readEntries(); // Continue reading until done
         }, reject);
      }

      readEntries();
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
      URL.revokeObjectURL(file);  // Free memory once done

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