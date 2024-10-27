import { createFile, createThumbnail, patchFile } from "@/api/files.js"

import { useUploadStore } from "@/stores/uploadStore.js"
import { useMainStore } from "@/stores/mainStore.js"
import { useToast } from "vue-toastification"
import { attachmentType, discordFileName, uploadStatus, uploadType } from "@/utils/constants.js"
import { detectExtension, getFileId, getOrCreateFolder, getVideoCover, isVideoFile } from "@/utils/uploadHelper.js"
import { encrypt } from "@/utils/encryption.js"
import { discord_instance } from "@/utils/networker.js"
import buttons from "@/utils/buttons.js"
import i18n from "@/i18n/index.js"


const toast = useToast()


export async function convertUploadInput(type, folder_context, uploadInput) {
   /**
    This method converts different uploadInputs into 1, standard one
    */
   if (type === uploadType.filesInput) {

   } else if (type === uploadType.folderInput) {

   } else if (type === uploadType.filesDragAndDrop) {

   } else if (type === uploadType.folderDragAndDrop) {

   } else {
      console.error("convertUploadInput: invalid type: " + type)
   }

}

export async function* prepareRequests() {
   /**
    this is a generator function!
    */

   const uploadStore = useUploadStore()
   const mainStore = useMainStore()
   let chunkSize = mainStore.user.maxDiscordMessageSize

   let totalSize = 0
   let attachments = []

   // eslint-disable-next-line no-constant-condition
   while (true) {

      let fileObj = await uploadStore.getFileFromQueue()
      if (!fileObj) break //we break if there are no more files in the queue

      //CASE 1, file is > 25mb
      if (fileObj.size > chunkSize) {
         //CASE 1.1, attachments already created, we yield the already created attachments in a request
         if (attachments.length !== 0) {
            let request = { "totalSize": totalSize, "attachments": attachments }
            totalSize = 0
            attachments = []
            yield request
         }

         //CASE 1.2 attachments are not created, we create chunked requests from the big file
         for (let j = 0; j < fileObj.systemFile.size; j += chunkSize) {
            let chunk = fileObj.systemFile.slice(j, j + chunkSize)

            let attachment = { "type": attachmentType.chunked, "fileObj": fileObj, "rawBlob": chunk, "fragment_sequence": j + 1 } //todo fragments shouldn't start at 1
            attachments.push(attachment)
            totalSize = totalSize + chunk.size

            //CASE 1.2.1 chunk size is already 25mb, so we yield it in a request
            if (totalSize === chunkSize) {
               let request = { "totalSize": totalSize, "attachments": attachments }
               totalSize = 0
               attachments = []
               yield request
            }
         }
      }
      //CASE 2. file is < 25mb
      else {
         //CASE 2.1 file is <25 mb but totalSize including fileObj.size is > 25mb or attachments.length == 10
         //we need to yield the already created attachments in a request
         if (totalSize + fileObj.size > chunkSize || attachments.length === 10) {
            let request = { "totalSize": totalSize, "attachments": attachments }
            totalSize = 0
            attachments = []
            yield request
         }

         //CASE 2.2 file is < 25mb and attachments length < 10, and we can safely add it to attachments
         let attachment = { "type": attachmentType.entireFile, "fileObj": fileObj, "rawBlob": fileObj.systemFile, "fragment_sequence": 1}
         attachments.push(attachment)
         totalSize = totalSize + fileObj.systemFile.size

      }

      //We now need to generate a thumbnail if needed.
      if (isVideoFile(fileObj.systemFile)) {
         let thumbnail = getVideoCover(fileObj.systemFile)

         //CASE 1, totalSize including thumbnail.size is > 25mb or attachments.length == 10
         if (totalSize + thumbnail.size > chunkSize || attachments.length === 10) {
            let request = { "totalSize": totalSize, "attachments": attachments }
            totalSize = 0
            attachments = []
            yield request
         }

         let attachment = { "type": attachmentType.thumbnail, "fileObj": fileObj, "rawBlob": thumbnail }
         attachments.push(attachment)
         totalSize = totalSize + thumbnail.size
      }

   }
   //we need to handle the already created attachments after break
   let request = { "totalSize": totalSize, "attachments": attachments }
   yield request
}

export async function preUploadRequest(request) {
   const mainStore = useMainStore()

   let files = []
   for (let i = 0; i < request.attachments.length; i++) {
      let fileObj = request.attachments[i].fileObj

      let folderId = await getOrCreateFolder(fileObj.path)
      request.attachments[i].fileObj.parent_id = folderId

      let file_id = await getFileId(fileObj)
      if (file_id) {
         request.attachments[i].fileObj.file_id = file_id
      } else {
         let attachment = request.attachments[i]

         let file_data = {
            "name": fileObj.file.name,
            "parent_id": folderId,
            "mimetype": fileObj.file.type,
            "extension": detectExtension(fileObj.file.name),
            "size": fileObj.file.size,
            "index": i,
            "is_encrypted": mainStore.settings.encryptFiles,
            "encryption_method": parseInt(mainStore.settings.encryptionMethod)
         }
         if (attachment.type === attachmentType.thumbnail) {
            console.warn("ERROR: file has not been yet created, thumbnail cannot be created!")
            // console.warn("Attempting to create it, possible race conditions...")
            // let thumbnail_file = await createFile([file_data], { __displayErrorToast: false })
            // request.attachments[i].fileObj.file_id = file_id
         }
         files.push(file_data)
      }
   }
   let backendFiles = await createFile(files)

   //monkey patch file and folder id to request attachment fileobjs

}

export async function uploadRequest(request) {
   const uploadStore = useUploadStore()
   const mainStore = useUploadStore()

   uploadStore.currentRequests.push(request)

   request = preUploadRequest(request)

   let attachmentJson = []
   let fileFormList = new FormData()
   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i];

      let encryptedBlob = await encrypt(attachment)

      fileFormList.append(`files[${i}]`, encryptedBlob, discordFileName)
      attachmentJson.push({
         "id": i,
         "filename": discordFileName
      })
   }

   let webhook = mainStore.settings.webhook
   fileFormList.append("json_payload", JSON.stringify({ "attachments": attachmentJson }))

   let discord_response = await discord_instance.post(webhook, fileFormList, {
      headers: {
         "Content-Type": "multipart/form-data"
      },
      onUploadProgress: function(progressEvent) {


      }
   })

   let filesData = []

   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i];

      if (attachment.type === attachmentType.entireFile) {
         //set status to finishing
         uploadStore.setStatus(attachment.fileObj.file_id, uploadStatus.finishing)

         let file_data = {
            "file_id": attachment.fileObj.file_id,
            "fragment_sequence": attachment.fragment_sequence,
            "fragment_size": attachment.fileObj.systemFile.size,
            "message_id": discord_response.data.id,
            "attachment_id": discord_response.data.attachments[i].id
         }
         filesData.push(file_data)
      }
      else if(attachment.type === attachmentType.thumbnail) {
         await saveThumbnail(attachment)
      }
   }

   await patchFile({ "files": filesData })
   for (let file of filesData) {
      uploadStore.finishFileUpload(file.file_id)
   }

   buttons.success("upload")

   uploadStore.currentRequests--
   uploadStore.uploadSpeedMap.delete(request.requestId)
   uploadStore.processUploads()


}

export async function saveThumbnail(attachment) {
   const mainStore = useMainStore()
   const uploadStore = useUploadStore()

   let file_id = await getFileId(attachment.fileObj)
   let fileObj = attachment.fileObj

   let thumbnail = await encrypt(attachment)

   let formData = new FormData()
   formData.append("file", thumbnail, discordFileName)
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

}


