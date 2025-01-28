
import { useUploadStore } from "@/stores/uploadStore.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, uploadStatus } from "@/utils/constants.js"
import {
   generateKey,
   generateIv,
   getOrCreateFolder,
   getVideoCover,
   getWebhook,
   isVideoFile
} from "@/utils/uploadHelper.js"
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
      queueFile.fileObj.folderId = await getOrCreateFolder(queueFile.fileObj)
      queueFile.fileObj.totalChunks = Math.ceil(queueFile.fileObj.size / chunkSize)
      queueFile.fileObj.iv = generateIv(queueFile.fileObj)
      queueFile.fileObj.key = generateKey()

      //generating a thumbnail if needed.
      if (isVideoFile(queueFile)) {
         try {
            let { thumbnail, duration } = await getVideoCover(queueFile)

            queueFile.fileObj.duration = Math.round(duration)
            queueFile.fileObj.thumbnail = true

            //CASE 1, totalSize including thumbnail.size is > 10Mb or attachments.length == 10
            if (totalSize + thumbnail.size > chunkSize || attachments.length === 10) {
               let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
               totalSize = 0
               attachments = []
               webhook = getWebhook(webhook)
               yield request
            }

            let attachment = { "type": attachmentType.thumbnail, "fileObj": queueFile.fileObj, "rawBlob": thumbnail }
            attachment.iv = generateIv(queueFile.fileObj)
            attachment.key = generateKey()

            attachments.push(attachment)
            totalSize = totalSize + thumbnail.size
         } catch (e) {
            console.log(e)
            toast.error("Couldn't get thumbnail for: " + queueFile.fileObj.name)
         }

      }

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

   }
   //we need to handle the already created attachments after break
   if (attachments.length > 0) {
      let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments, "id": uuidv4() }
      yield request
   }

}

export async function uploadRequest(request) {
   const uploadStore = useUploadStore()
   let attachmentName = uploadStore.attachmentName

   let attachmentJson = []
   let fileFormList = new FormData()
   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i]

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


   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i]
      let discordAttachment = discordResponse.data.attachments[i]
      await uploadStore.fillAttachmentInfo(attachment, request, discordResponse, discordAttachment)
   }

   uploadStore.finishRequest(request.id)
}



