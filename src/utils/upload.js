import {create} from "@/api/folder.js"
import i18n from "@/i18n/index.js"
import {createFile, patchFile} from "@/api/files.js"

import {useUploadStore} from "@/stores/uploadStore.js"
import {useMainStore} from "@/stores/mainStore.js"
import {useToast} from "vue-toastification"
import {discord_instance} from "@/utils/networker.js"
import {chunkSize} from "@/utils/constants.js"
import buttons from "@/utils/buttons.js";


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
export function scanFiles(dt) {
   return new Promise((resolve) => {
      let reading = 0
      const contents = []

      if (dt.items !== undefined) {
         for (let item of dt.items) {
            if (
               item.kind === "file" &&
               typeof item.webkitGetAsEntry === "function"
            ) {
               const entry = item.webkitGetAsEntry()
               readEntry(entry)
            }
         }
      } else {
         resolve(dt.files)
      }

      function readEntry(entry, directory = "") {
         if (entry.isFile) {
            reading++
            entry.file((file) => {
               reading--

               file.webkitRelativePath = `${directory}${file.name}`
               contents.push(file)

               if (reading === 0) {
                  resolve(contents)
               }
            })
         } else if (entry.isDirectory) {

            readReaderContent(entry.createReader(), `${directory}${entry.name}`)
         }
      }

      function readReaderContent(reader, directory) {
         reading++

         reader.readEntries(function (entries) {
            reading--
            if (entries.length > 0) {
               for (const entry of entries) {
                  readEntry(entry, `${directory}/`)
               }

               readReaderContent(reader, `${directory}/`)
            }

            if (reading === 0) {
               resolve(contents)
            }
         })
      }
   })
}

function detectExtension(filename) {
   let arry = filename.split(".")

   return "." + arry[arry.length - 1]

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
         let folder_list_str = folder_list.join("/") // convert that list to str "example:
         // folder_list_str np: "nowyFolder/kolejnyFolder"

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
                  let message = i18n.global.t('toasts.folderCreated', {name: chatgpt_folder_name}).toString()

                  toast.success(message)
               }

               folder = await create({"parent_id": parent_list_id, "name": chatgpt_folder_name})
               folder_structure[folder_list_key] = {"id": folder.id, "parent_id": parent_list_id}

            }
         }
         fileList.push({"parent_id": folder.id, "file": file})

      }
   } else {
      // jeżeli uploadujemy pliki a nie foldery to nie musimy sie bawić w to całe gówno jak na górze XD
      for (let file of files) {
         fileList.push({"parent_id": parent_folder.id, "file": file})
      }
   }
   return fileList
}

async function createFiles(fileList, filesInRequest) {
   let createdFiles = []

   let file_res = await createFile({"files": filesInRequest})


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
   createdFiles.push(...await createFiles(fileList, filesInRequest))
   /**
    createdFiles looks like this:
    "file_id": created_file.file_id, "encryption_key": created_file.key, "file": file, "parent_id": created_file.parent_id, "name": created_file.name}
    */
   return createdFiles
}
export async function prepareRequests() {
   const uploadStore = useUploadStore()

   let totalSize = 0
   let fileFormList = new FormData()
   let attachmentJson = []
   let filesForRequest = []


   let i = 0
   while (totalSize < chunkSize || filesForRequest.length >= 10) {


      let fileObj = await uploadStore.getFileFromQueue()
      if (!fileObj) break
      try {

         let workingFile = fileObj.systemFile
         if (fileObj.is_encrypted) {
            workingFile = await encrypt(fileObj.encryption_key, fileObj.encryption_iv, fileObj.systemFile)
         }
         let size = workingFile.size

         if (size !== 0) {
            if (size > chunkSize) {

               let chunks = []
               for (let j = 0; j < size; j += chunkSize) {
                  let chunk = workingFile.slice(j, j + chunkSize)
                  chunks.push(chunk)
               }

               let requestList = []
               for (let j = 0; j < chunks.length; j++) {
                  let request = {"type": "chunked", "fileObj": fileObj, "chunk": chunks[j], "chunkNumber": j + 1, "totalChunks": chunks.length}
                  requestList.push(request)
               }
               return requestList


            } else {

               if (totalSize + size > chunkSize || filesForRequest.length >= 10) {
                  return [{"type": "multiAttachment", "fileFormList": fileFormList, "attachmentJson": attachmentJson, "filesForRequest": filesForRequest}]

               }
               filesForRequest.push(fileObj)
               fileFormList.append(`files[${i}]`, workingFile, `custom_filename_here${i}`)
               attachmentJson.push({
                  "id": i,
                  "filename": `custom_filename_here${i}`
               })
               totalSize = totalSize + size
            }
         }
         i++
      }
      catch (e) {
         console.error(e)
         uploadStore.setStatus(fileObj.file_id, "failed")
      }
   }
   if (attachmentJson.length > 0) {
      return [{"type": "multiAttachment", "fileFormList": fileFormList, "attachmentJson": attachmentJson, "filesForRequest": filesForRequest}]
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

   }
   catch (e) {
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

   fileFormList.append('json_payload', JSON.stringify({"attachments": attachmentJson}))
   let file_ids = filesForRequest.map(obj => obj.file_id)

   let response = await discord_instance.post(webhook, fileFormList, {
      headers: {
         'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: function (progressEvent) {
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
         "attachment_id": attachment.id,

      }
      response_list.push(file_data)

   }

   await patchFile({"files": response_list})
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


   formData.append('file', chunk, `chunk_${chunkNumber}`)

   let response = await discord_instance.post(webhook, formData, {
      headers: {
         'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: function (progressEvent) {

         uploadStore.setUploadSpeedBytes(requestId, progressEvent.rate)
         uploadStore.setETA(requestId, progressEvent.estimated)

         uploadStore.setProgress(fileObj.file_id, progressEvent.bytes)

      }
   })


   let file_data = {
      "file_id": fileObj.file_id, "fragment_sequence": chunkNumber, "total_fragments": totalChunks,
      "fragment_size": chunk.size, "message_id": response.data.id, "attachment_id": response.data.attachments[0].id
   }
   let res = await patchFile({"files": [file_data]})

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

   let algorithm = {name: 'AES-CTR', counter: iv, length: 64}
   let cryptoKey = await crypto.subtle.importKey(
      'raw',
      key,
      algorithm,
      false,
      ['encrypt']
   )
   console.log(3333)

   let arrayBuffer = await file.arrayBuffer()
   let encryptedArrayBuffer = await crypto.subtle.encrypt(
      {name: 'AES-CTR', counter: iv, length: 64},
      cryptoKey,
      arrayBuffer
   )
   console.log(444)

   return new Blob([new Uint8Array(encryptedArrayBuffer)])
}