import { createFile, createThumbnail, patchFile } from "@/api/files.js"

import { useUploadStore } from "@/stores/uploadStore.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, uploadStatus } from "@/utils/constants.js"
import { detectExtension, detectType, generateThumbnailIv, getFileId, getOrCreateFolder, getVideoCover, getWebhook, isVideoFile } from "@/utils/uploadHelper.js"
import { encrypt } from "@/utils/encryption.js"
import { discordInstance } from "@/utils/networker.js"
import { v4 as uuidv4 } from "uuid"
import { useToast } from "vue-toastification"

const toast = useToast()

export async function* prepareRequests() {
   /**
    this is a generator function!
    */

   const uploadStore = useUploadStore()
   const mainStore = useMainStore()
   let chunkSize = mainStore.user.maxDiscordMessageSize

   let totalSize = 0
   let attachments = []
   let webhook = uploadStore.webhooks[0]
   let queueFile
   while ((queueFile = uploadStore.getFileFromQueue())) {

      //CASE 1, file is > 10Mb
      if (queueFile.fileObj.size > chunkSize) {
         //CASE 1.1, attachments already created, we yield the already created attachments in a request
         if (attachments.length !== 0) {
            let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
            totalSize = 0
            attachments = []
            webhook = getWebhook(webhook)
            yield request
         }

         //CASE 1.2 attachments are not created, we create chunked requests from the big file
         let i = 0
         for (let j = 0; j < queueFile.fileObj.size; j += chunkSize) {
            let chunk = queueFile.systemFile.slice(j, j + chunkSize)

            let attachment = { "type": attachmentType.chunked, "fileObj": queueFile.fileObj, "rawBlob": chunk, "fragmentSequence": i + 1 } //todo fragments shouldn't start at 1
            attachments.push(attachment)
            totalSize = totalSize + chunk.size

            //CASE 1.2.1 chunk size is already 10Mb, so we yield it in a request
            if (totalSize === chunkSize) {
               let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
               totalSize = 0
               attachments = []
               webhook = getWebhook(webhook)
               yield request
            }
            i++
         }
      }
      //CASE 2. file is < 10Mb
      else {
         //CASE 2.1 file is <10Mb but totalSize including fileObj.size is > 10Mb or attachments.length == 10
         //we need to yield the already created attachments in a request
         if (totalSize + queueFile.systemFile.size > chunkSize || attachments.length === 10) {
            let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
            totalSize = 0
            attachments = []
            webhook = getWebhook(webhook)
            yield request
         }

         //CASE 2.2 file is < 10Mb and attachments length < 10, and we can safely add it to attachments
         let attachment = { "type": attachmentType.entireFile, "fileObj": queueFile.fileObj, "rawBlob": queueFile.systemFile, "fragmentSequence": 1 }
         attachments.push(attachment)
         totalSize = totalSize + queueFile.systemFile.size
      }

      //We now need to generate a thumbnail if needed.
      if (isVideoFile(queueFile)) {
         try {
            let thumbnail = await getVideoCover(queueFile)

            //CASE 1, totalSize including thumbnail.size is > 10Mb or attachments.length == 10
            if (totalSize + thumbnail.size > chunkSize || attachments.length === 10) {
               let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
               totalSize = 0
               attachments = []
               webhook = getWebhook(webhook)
               yield request
            }


            let attachment = { "type": attachmentType.thumbnail, "fileObj": queueFile.fileObj, "rawBlob": thumbnail }
            attachments.push(attachment)
            totalSize = totalSize + thumbnail.size
         } catch (e) {
            toast.error("Couldn't get thumbnail for: " + queueFile.fileObj.name)
         }

      }

   }
   //we need to handle the already created attachments after break
   if (attachments.length > 0) {
      let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments, "id": uuidv4() }
      yield request
   }

}

export async function preUploadRequest(request) {
   let uploadStore = useUploadStore()
   let files = []
   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i]
      if (attachment.type === attachmentType.entireFile || attachment.type === attachmentType.chunked) {
         let fileObj = request.attachments[i].fileObj

         let folderId = await getOrCreateFolder(fileObj)
         request.attachments[i].fileObj.parent_id = folderId

         let file_id = await getFileId(fileObj)
         if (file_id) {
            request.attachments[i].fileObj.fileId = file_id
         } else {
            uploadStore.setStatus(fileObj.frontendId, uploadStatus.creating)
            let file_data = {
               "name": fileObj.name,
               "parent_id": folderId,
               "mimetype": detectType(fileObj),
               "extension": detectExtension(fileObj.name),
               "size": fileObj.size,
               "frontend_id": fileObj.frontendId,
               "encryption_method": parseInt(fileObj.encryptionMethod),
               "created_at": fileObj.createdAt
            }
            files.push(file_data)
         }
      }
   }
   if (files.length > 0) {
      let backendFiles = await createFile({ "files": files })

      // Monkey patch file_id, key, iv to request attachments
      backendFiles.forEach(backendFile => {
         uploadStore.setStatus(backendFile.frontend_id, uploadStatus.encrypting)

         let matchingAttachment = request.attachments.find(att => att.fileObj.frontendId === backendFile.frontend_id)
         if (matchingAttachment) {
            matchingAttachment.fileObj.fileId = backendFile.file_id
            matchingAttachment.fileObj.encryptionKey = backendFile.key
            matchingAttachment.fileObj.encryptionIv = backendFile.iv

            //save created file_id for future attachments
            uploadStore.createdFiles[matchingAttachment.fileObj.frontendId] = backendFile.file_id
         }
      })
   }
   return request

}

export async function uploadRequest(request) {
   const uploadStore = useUploadStore()
   let attachmentName = uploadStore.attachmentName

   let attachmentJson = []
   let fileFormList = new FormData()
   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i]

      //we have to generate a new iv to not reuse the file one
      if (attachment.type === attachmentType.thumbnail) {
         attachment.iv = generateThumbnailIv(attachment.fileObj)
      }

      let encryptedBlob = await encrypt(attachment)
      uploadStore.setStatus(attachment.fileObj.frontendId, uploadStatus.uploading)

      fileFormList.append(`files[${i}]`, encryptedBlob, attachmentName)
      attachmentJson.push({
         "id": i,
         "filename": attachmentName
      })
   }

   fileFormList.append("json_payload", JSON.stringify({ "attachments": attachmentJson }))

   let discordResponse = await discordInstance.post(request.webhook.url, fileFormList, {
      headers: {
         "Content-Type": "multipart/form-data"
      },
      onUploadProgress: function(progressEvent) {
         uploadStore.onUploadProgress(request, progressEvent)
      }


   })
   await afterUploadRequest(request, discordResponse)


}

export async function afterUploadRequest(request, discordResponse) {
   const uploadStore = useUploadStore()

   uploadStore.decrementRequests()
   let filesData = []
   let thumbnailData = []

   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i]

      if (attachment.type === attachmentType.entireFile || attachment.type === attachmentType.chunked) {
         if (attachment.type === attachmentType.entireFile) {
            //set status to finishing
            uploadStore.setStatus(attachment.fileObj.frontendId, uploadStatus.finishing)
         }

         let file_data = {
            "frontend_id": attachment.fileObj.frontendId,
            "file_id": attachment.fileObj.fileId,
            "fragment_sequence": attachment.fragmentSequence,
            "fragment_size": attachment.rawBlob.size,
            "message_id": discordResponse.data.id,
            "attachment_id": discordResponse.data.attachments[i].id,
            "webhook": request.webhook.discord_id
         }
         filesData.push(file_data)

      } else if (attachment.type === attachmentType.thumbnail) {
         let thumbnail_data = {
            "file_id": attachment.fileObj.fileId,
            "size": attachment.rawBlob.size,
            "message_id": discordResponse.data.id,
            "attachment_id": discordResponse.data.attachments[i].id,
            "iv": attachment.iv,
            "webhook": request.webhook.discord_id

         }
         thumbnailData.push(thumbnail_data)

      }
   }
   if (filesData.length > 0) {
      let backendResponse = await patchFile({ "files": filesData })

      backendResponse.forEach(backendFile => {
         if (backendFile.ready) {
            uploadStore.finishFileUpload(backendFile.frontend_id)
         }
      })
   }
   if (thumbnailData.length > 0) {
      await createThumbnail({ "thumbnails": thumbnailData })

   }

   uploadStore.finishRequest(request.id)
}



