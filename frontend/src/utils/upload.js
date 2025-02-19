import { useUploadStore } from "@/stores/uploadStore.js"
import { useMainStore } from "@/stores/mainStore.js"
import { attachmentType, encryptionMethod, fileUploadStatus, uploadState } from "@/utils/constants.js"
import {
   generateIv,
   generateKey,
   getAudioCover,
   getOrCreateFolder,
   getVideoCover,
   getWebhook,
   isAudioFile,
   isVideoFile,
   roundUpTo64, upload
} from "@/utils/uploadHelper.js"
import { encrypt, encryptAttachment } from "@/utils/encryption.js"
import { backendInstance, uploadInstance } from "@/utils/networker.js"
import { useToast } from "vue-toastification"
import axios from "axios"

const toast = useToast()

export async function* prepareRequests() {
   /**
    this is a generator function!
    */
   const uploadStore = useUploadStore()
   const mainStore = useMainStore()
   let maxChunkSize = mainStore.user.maxDiscordMessageSize

   let totalSize = 0
   let attachments = []
   let webhook = uploadStore.webhooks[0]
   let queueFile
   while ((queueFile = uploadStore.getFileFromQueue())) {
      //creating folder if needed and getting it's backend ID
      queueFile.fileObj.folderId = await getOrCreateFolder(queueFile.fileObj)
      if (queueFile.fileObj.encryptionMethod !== encryptionMethod.NotEncrypted) {
         queueFile.fileObj.iv = generateIv(queueFile.fileObj.encryptionMethod)
         queueFile.fileObj.key = generateKey()
      }

      let thumbnail
      //extracting cover if needed
      if (isAudioFile(queueFile)) {
         try {
            thumbnail = await getAudioCover(queueFile)
         } catch (e) {
            toast.warning("Couldn't get cover for: " + queueFile.fileObj.name)
            console.warn(e)
         }
      }
      //generating a thumbnail if needed.
      if (isVideoFile(queueFile)) {
         try {
            let data = await getVideoCover(queueFile)
            let duration = data.duration
            thumbnail = data.thumbnail
            queueFile.fileObj.duration = Math.round(duration)

         } catch (e) {
            console.log(e)
            toast.error("Couldn't get thumbnail for: " + queueFile.fileObj.name)
         }
      }

      //if cover/thumbnail exist(they can never exist both at the same time) we generate a request with them
      if (thumbnail) {
         queueFile.fileObj.thumbnail = true

         //CASE 1, totalSize including thumbnail.size is > 10Mb or attachments.length == 10
         if (totalSize + thumbnail.size > maxChunkSize || attachments.length === 10) {
            let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
            totalSize = 0
            attachments = []
            webhook = getWebhook(webhook)
            yield request
         }

         //else we add it
         let attachment = { "type": attachmentType.thumbnail, "fileObj": queueFile.fileObj, "rawBlob": thumbnail }
         if (queueFile.fileObj.encryptionMethod !== encryptionMethod.NotEncrypted) {
            attachment.iv = generateIv(queueFile.fileObj.encryptionMethod)
            attachment.key = generateKey()
         }

         attachments.push(attachment)
         //rounding to 64 as padding for encryption
         totalSize += roundUpTo64(thumbnail.size)
      }

      //If theres to little space left in the request, we yield to prevent for example the beginning of a video having 0.5mb which would cause multiple messages
      // that have to be loaded before playback starts

      if (totalSize > maxChunkSize / 2 || attachments.length === 10) {
         let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
         totalSize = 0
         attachments = []
         webhook = getWebhook(webhook)
         yield request
      }


      //CASE 1.2 attachments are not created, we create chunked requests from the big file
      let i = 0
      let fileSize = queueFile.fileObj.size
      let offset = 0
      while (offset < fileSize) {

         let remainingSpace = maxChunkSize - totalSize
         let remainingFileSize = fileSize - offset
         let chunkSizeToTake = Math.min(remainingSpace, remainingFileSize)

         let chunk = queueFile.systemFile.slice(offset, offset + chunkSizeToTake)

         let attachment = {
            "type": attachmentType.file,
            "fileObj": queueFile.fileObj,
            "rawBlob": chunk,
            "fragmentSequence": i + 1,
            "offset": offset
         }

         attachments.push(attachment)
         totalSize += roundUpTo64(chunk.size)
         offset += chunk.size
         i++

         // we have to yield
         if (totalSize >= maxChunkSize || attachments.length >= 9) {
            yield { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
            totalSize = 0
            attachments = []
            webhook = getWebhook(webhook)
         }
      }
      //we need to inform about totalChunks of a file
      queueFile.fileObj.totalChunks = i
   }
   //we need to handle the already created attachments after break
   if (attachments.length > 0) {
      let request = { "webhook": webhook, "totalSize": totalSize, "attachments": attachments }
      yield request
   }

}

export async function uploadRequest(request) {
   const uploadStore = useUploadStore()

   let attachmentName = uploadStore.attachmentName

   if (uploadStore.state === uploadState.paused) {
      uploadStore.addPausedRequest(request)
      return
   }
   let cancelTokenSource = axios.CancelToken.source()

   let attachmentJson = []
   let fileFormList = new FormData()
   for (let i = 0; i < request.attachments.length; i++) {
      let attachment = request.attachments[i]

      let encryptedBlob = await encryptAttachment(attachment)
      uploadStore.setStatus(attachment.fileObj.frontendId, fileUploadStatus.uploading)

      fileFormList.append(`files[${i}]`, encryptedBlob, attachmentName)
      attachmentJson.push({
         "id": i,
         "filename": attachmentName
      })
   }
   fileFormList.append("json_payload", JSON.stringify({ "attachments": attachmentJson }))


   let bytesUploaded = 0
   let startTime = Date.now()

   uploadStore.addCancelToken(request.id, cancelTokenSource)
   let config = {
      onUploadProgress: function(progressEvent) {
         bytesUploaded = progressEvent.loaded

         if (!progressEvent.rate) {
            let elapsedTime = (Date.now() - startTime) / 1000
            progressEvent.rate = bytesUploaded / elapsedTime / 20 //todo fix this
         }
         uploadStore.onUploadProgress(request, progressEvent)
      },

      cancelToken: cancelTokenSource.token

   }
   let uploadResponse = await upload(fileFormList, config, request.webhook.url).catch(err => {
      if(axios.isCancel(err)) {
         uploadStore.addPausedRequest(request)
         uploadStore.decrementRequests()

      }
      uploadStore.onUploadError(request, bytesUploaded)
      throw err
   })
   await afterUploadRequest(request, uploadResponse)
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



