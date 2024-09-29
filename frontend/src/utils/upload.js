import { create } from "@/api/folder.js"
import i18n from "@/i18n/index.js"
import { createFile, createThumbnail, patchFile } from "@/api/files.js"

import { useUploadStore } from "@/stores/uploadStore.js"
import { useMainStore } from "@/stores/mainStore.js"
import { useToast } from "vue-toastification"
import { discord_instance } from "@/utils/networker.js"
import { chunkSize } from "@/utils/constants.js"
import buttons from "@/utils/buttons.js"


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

export async function scanFiles(dataTransfer) {
   let files = [];
   let items = dataTransfer.items;

   for (let i = 0; i < items.length; i++) {
      const item = items[i].webkitGetAsEntry(); // Get the entry (file or folder)

      if (item) {
         if (item.isFile) {
            // Process and add the file with its path
            files.push(await processFile(item, ""));
         } else if (item.isDirectory) {
            // Process directory and add files recursively with paths
            files = files.concat(await processDirectory(item, ""));
         }
      }
   }

   console.log("Scanned Files:");
   console.log(files);
}

// Process individual file (returns a Promise to read the file and add path)
function processFile(fileEntry, path) {
   return new Promise((resolve, reject) => {
      fileEntry.file(function(file) {
         // Return both the file and its relative path
         const filePath = path ? `${path}/${fileEntry.name}` : fileEntry.name; // No leading slash for root level
         resolve({ file, path: filePath });
      }, reject);
   });
}

// Process directory (recursively read contents and return all files with paths)
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
                  files.push(await processFile(entry, currentPath)); // Process file with path
               } else if (entry.isDirectory) {
                  files = files.concat(await processDirectory(entry, currentPath)); // Recursively process folder
               }
            }

            readEntries(); // Continue reading until done
         }, reject);
      }

      readEntries();
   });
}


function detectExtension(filename) {
   let arry = filename.split(".")

   if (arry.length === 1) return ".txt" //missing extension defaults to .txt
   return "." + arry[arry.length - 1]

}

function isVideoFile(file) {
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

function getVideoCover(file, seekTo = 0.0) {
   console.log("getting video cover for file: ", file)
   return new Promise((resolve, reject) => {
      // load the file to a video player
      const videoPlayer = document.createElement("video")
      videoPlayer.setAttribute("src", URL.createObjectURL(file))
      videoPlayer.load()
      videoPlayer.addEventListener("error", (ex) => {
         reject("error when loading video file", ex)
      })
      // load metadata of the video to get video duration and dimensions
      videoPlayer.addEventListener("loadedmetadata", () => {

         // seek to user defined timestamp (in seconds) if possible
         if (videoPlayer.duration < seekTo) {
            console.warn("video is too short.")
            seekTo = 0.0
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
   })
}

async function generateThumbnail(fileObj) {
   const mainStore = useMainStore()
   const uploadStore = useUploadStore()
   uploadStore.setStatus(fileObj.file_id, "generatingThumbnail")

   try {
      let thumbnail = await getVideoCover(fileObj.unecryptedFile)

      if (fileObj.is_encrypted)
         thumbnail = await encrypt(fileObj.encryption_key, fileObj.encryption_iv, thumbnail)


      let formData = new FormData()
      formData.append("file", thumbnail, `Kocham Alternatywki`)

      let webhook = mainStore.settings.webhook

      let response = await discord_instance.post(webhook, formData, {
         headers: {
            "Content-Type": "multipart/form-data"
         }

      })

      let file_data = {
         "file_id": fileObj.file_id,
         "size": thumbnail.size,
         "message_id": response.data.id,
         "attachment_id": response.data.attachments[0].id
      }

      await createThumbnail(file_data)

   } catch (err) {
      console.error(err)
      const toast = useToast()
      toast.error(i18n.global.t("toasts.thumbnailError", { name: fileObj.name }))
   }

}

export async function createNeededFolders(files, parent_folder) {
   /**
    * This function creates all folders needed for upload,
    * and also creates a nice file structure with it's corresponding parent folder id
    *
    * {fileList} = {file: file, parent_id: parent_id}
    *
    * @param {event.currentTarget.files} files - list of file objects
    * @param {string} parent_folder - folder object in which to upload to
    */


      // check if we are uploading a folder or just files
   let folder_upload =
         files[0].webkitRelativePath !== undefined &&
         files[0].webkitRelativePath !== ""

   let fileList = []
   let folder = parent_folder
   //if we are uploading a folder, we need to create all folders that don't already exist
   if (folder_upload) {
      let folder_structure = {}

      for (let file of files) {
         console.log("====file====")
         // file.webkitRelativePath np: "nowyFolder/kolejnyFolder/plik.ext"
         let folder_list = file.webkitRelativePath.split("/").slice(0, -1)  // Get list of folders by removing the file name
         // folder_list np: ['nowyFolder', 'kolejnyFolder']


         for (let i = 1; i <= folder_list.length; i++) {
            // idziemy od tyłu po liscie czyli jesli lista to np [a1, b2, c3, d4, e5, f6]
            // to najpierw bedziemy mieli a1
            // potem a1, b2
            // potem a1, b2, c3
            let folder_list_key = folder_list.slice(0, i).join("/")
            if (!(folder_list_key in folder_structure)) {

               // zapytanie API
               // stwórz folder o nazwie folder_list[0:i][-1] z parent_id = file_structure[folder_list[0:i-1]]
               let parent_list = folder_structure[folder_list.slice(0, i - 1).join("/")]
               let parent_list_id
               let chatgpt_folder_name = folder_list.slice(0, i)[folder_list.slice(0, i).length - 1]

               if (parent_list) {
                  parent_list_id = parent_list["id"]
               } else {
                  parent_list_id = parent_folder.id
                  let message = i18n.global.t("toasts.folderCreated", { name: chatgpt_folder_name }).toString()

                  toast.success(message)
               }

               folder = await create({ "parent_id": parent_list_id, "name": chatgpt_folder_name })
               folder_structure[folder_list_key] = { "id": folder.id, "parent_id": parent_list_id }

            }
         }
         fileList.push({ "parent_id": folder.id, "file": file })

      }
   } else {
      // jeżeli uploadujemy pliki a nie foldery to nie musimy sie bawić w to całe gówno jak na górze XD
      for (let file of files) {
         fileList.push({ "parent_id": parent_folder.id, "file": file })
      }
   }
   return fileList
}

async function createFiles(fileList, filesInRequest) {
   let createdFiles = []

   let file_res = await createFile({ "files": filesInRequest })


   for (let created_file of file_res) {
      let file = fileList[created_file.index].file

      createdFiles.push({
         "file_id": created_file.file_id, "encryption_key": created_file.key, "encryption_iv": created_file.iv, "file": file,
         "parent_id": created_file.parent_id, "name": created_file.name, "type": created_file.type, "is_encrypted": created_file.is_encrypted
      })
   }
   return createdFiles
}

export async function handleCreatingFiles(fileList) {
   const mainStore = useMainStore()

   console.log(fileList)
   //sortujemy rozmiarami
   fileList.sort((a, b) => a.file.size - b.file.size)
   let createdFiles = []
   let filesInRequest = []

   for (let i = 0; i < fileList.length; i++) {
      let fileObj = fileList[i]
      console.log("fileObj")
      console.log(fileObj)

      let file_obj =
         {
            "name": fileObj.file.name,
            "parent_id": fileObj.parent_id,
            "mimetype": fileObj.file.type,
            "extension": detectExtension(fileObj.file.name),
            "size": fileObj.file.size,
            "index": i,
            "is_encrypted": mainStore.settings.encryptFiles
         }

      filesInRequest.push(file_obj)
      if (filesInRequest.length >= 100) {
         createdFiles.push(...await createFiles(fileList, filesInRequest))
         filesInRequest = []
      }
   }
   if (filesInRequest.length > 0) {
      createdFiles.push(...await createFiles(fileList, filesInRequest))
   }
   /**
    createdFiles looks like this:
    "file_id": created_file.file_id, "encryption_key": created_file.key, "file": file, "parent_id": created_file.parent_id, "name": created_file.name}
    */
   return createdFiles
}


export async function prepareRequests() {
   const uploadStore = useUploadStore()

   let totalSize = 0
   let filesForRequest = []
   let attachmentJson = []
   let fileFormList = new FormData()


   let peekFile = null
   let fileObj = null
   try {
      // if peekFile.size > 25MB we either return previously created multiAttachment request,
      // or if it doesn't exist, we create a new chunked requests from that peeked file
      let i = 0
      // eslint-disable-next-line no-constant-condition
      while (true) {

         peekFile = uploadStore.queue[0]
         if (!peekFile) break
         //CASE 1, file is > 25mb
         if (peekFile.size > chunkSize) {

            //CASE 1.1, multiAttachment request already created, we break to exit the loop and handle it below
            if (filesForRequest.length !== 0) {
               break
            }

            //CAS 1.2 multiAttachment request is not created, we create chunked requests from peekFile
            fileObj = await uploadStore.getFileFromQueue()
            if (!fileObj) break

            //generate thumbnail if needed
            if (isVideoFile(fileObj.systemFile)) {
               await generateThumbnail(fileObj)
            }

            let chunks = []
            for (let j = 0; j < fileObj.systemFile.size; j += chunkSize) {
               let chunk = fileObj.systemFile.slice(j, j + chunkSize)
               chunks.push(chunk)
            }

            let requestList = []
            for (let j = 0; j < chunks.length; j++) {
               let request = { "type": "chunked", "fileObj": fileObj, "chunk": chunks[j], "chunkNumber": j + 1, "totalChunks": chunks.length }
               requestList.push(request)
            }
            return requestList
         }


         //CASE 2.1 file is <25 mb but total size including peekFile is > 25mb or filesForRequest + peekFile > 10
         //we need to return the already created multiAttachment request
         if (totalSize + peekFile.size > chunkSize || filesForRequest.length + 1 >= 10) {
            if (filesForRequest.length !== 0) {
               return [{ "type": "multiAttachment", "fileFormList": fileFormList, "attachmentJson": attachmentJson, "filesForRequest": filesForRequest }]
            }
         }

         //CASE 2.2 file is < 25mb, and we can safely add it to multiAttachment
         fileObj = await uploadStore.getFileFromQueue()
         if (!fileObj) break
         if (isVideoFile(fileObj.systemFile)) {
            await generateThumbnail(fileObj)
         }

         filesForRequest.push(fileObj)
         fileFormList.append(`files[${i}]`, fileObj.systemFile, `Kocham Alternatywki`)
         attachmentJson.push({
            "id": i,
            "filename": `Kocham Alternatywki`
         })
         totalSize = totalSize + fileObj.size
         i++

      }
      if (filesForRequest.length !== 0) {
         return [{ "type": "multiAttachment", "fileFormList": fileFormList, "attachmentJson": attachmentJson, "filesForRequest": filesForRequest }]
      }


   } catch (e) {
      console.error(e)
      if (fileObj) {
         uploadStore.setStatus(fileObj.file_id, "failed")
      } else if (peekFile) {
         uploadStore.setStatus(peekFile.file_id, "failed")

      }
   }

}

export async function uploadOneRequest(request, requestId) {
   const uploadStore = useUploadStore()

   try {
      if (request.type === "chunked") {
         await uploadChunk(request.chunk, request.chunkNumber, request.totalChunks, request.fileObj, requestId)

      }

      if (request.type === "multiAttachment") {
         await uploadMultiAttachments(request.fileFormList, request.attachmentJson, request.filesForRequest, requestId)
      }
      uploadStore.currentRequests--
      uploadStore.uploadSpeedMap.delete(requestId)
      uploadStore.processUploads()

   } catch (e) {
      console.error(e)

      if (request.type === "chunked") {
         uploadStore.setStatus(request.fileObj.file_id, "failed")
      }
      if (request.type === "multiAttachment") {
         for (let file of request.filesForRequest) {
            uploadStore.setStatus(file.file_id, "failed")

         }
      }
   }


}

export async function uploadMultiAttachments(fileFormList, attachmentJson, filesForRequest, requestId) {
   const uploadStore = useUploadStore()
   const mainStore = useMainStore()


   let webhook = mainStore.settings.webhook

   fileFormList.append("json_payload", JSON.stringify({ "attachments": attachmentJson }))
   let file_ids = filesForRequest.map(obj => obj.file_id)

   let response = await discord_instance.post(webhook, fileFormList, {
      headers: {
         "Content-Type": "multipart/form-data"
      },
      onUploadProgress: function(progressEvent) {
         uploadStore.setUploadSpeedBytes(requestId, progressEvent.rate)
         uploadStore.setETA(requestId, progressEvent.estimated)
         // Pass the progress details to Vuex
         uploadStore.setMultiAttachmentProgress(file_ids, progressEvent.progress)

      }
   })
   for (let file_id of file_ids) {
      uploadStore.setStatus(file_id, "finishing")
   }

   let response_list = []
   for (let i = 0; i < response.data.attachments.length; i++) {
      let attachment = response.data.attachments[i]

      let file_data = {
         "file_id": filesForRequest[i].file_id,
         "fragment_sequence": 1,
         "total_fragments": 1,
         "fragment_size": filesForRequest[i].systemFile.size,
         "message_id": response.data.id,
         "attachment_id": attachment.id

      }
      response_list.push(file_data)

   }

   await patchFile({ "files": response_list })
   for (let file_id of file_ids) {
      uploadStore.finishUpload(file_id)
   }

   buttons.success("upload")


}

export async function uploadChunk(chunk, chunkNumber, totalChunks, fileObj, requestId) {


   const uploadStore = useUploadStore()
   const mainStore = useMainStore()

   let webhook = mainStore.settings.webhook

   let formData = new FormData()


   formData.append("file", chunk, `Kocham Alternatywki`)

   let response = await discord_instance.post(webhook, formData, {
      headers: {
         "Content-Type": "multipart/form-data"
      },
      onUploadProgress: function(progressEvent) {

         uploadStore.setUploadSpeedBytes(requestId, progressEvent.rate)
         uploadStore.setETA(requestId, progressEvent.estimated)

         uploadStore.setProgress(fileObj.file_id, progressEvent.bytes)

      }
   })


   let file_data = {
      "file_id": fileObj.file_id, "fragment_sequence": chunkNumber, "total_fragments": totalChunks,
      "fragment_size": chunk.size, "message_id": response.data.id, "attachment_id": response.data.attachments[0].id
   }
   let res = await patchFile({ "files": [file_data] })

   //status 200 means the file is ready
   if (res.status === 200) {
      uploadStore.finishUpload(fileObj.file_id)
   }
   uploadStore.progressMap.delete(requestId)

}

function base64ToUint8Array(base64) {
   let binaryString = window.atob(base64)
   let len = binaryString.length
   let bytes = new Uint8Array(len)
   for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i)
   }
   return bytes
}

export async function encrypt(base64Key, base64IV, file) {
   console.log("base64Key")
   console.log(base64Key)
   console.log("base64IV")
   console.log(base64IV)

   console.log(1111)
   let key = base64ToUint8Array(base64Key) // Decode the base64 key to binary
   let iv = base64ToUint8Array(base64IV) // Decode the base64 key to binary
   console.log(222)

   let algorithm = { name: "AES-CTR", counter: iv, length: 64 }
   let cryptoKey = await crypto.subtle.importKey(
      "raw",
      key,
      algorithm,
      false,
      ["encrypt"]
   )
   console.log(3333)

   let arrayBuffer = await file.arrayBuffer()
   let encryptedArrayBuffer = await crypto.subtle.encrypt(
      { name: "AES-CTR", counter: iv, length: 64 },
      cryptoKey,
      arrayBuffer
   )
   console.log(444)

   return new Blob([new Uint8Array(encryptedArrayBuffer)], { type: file.type })
}