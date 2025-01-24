
import { attachmentType } from "@/utils/constants.js"
// import { generateThumbnailIv, getVideoCover, isVideoFile } from "@/utils/uploadHelper.js"
import { v4 as uuidv4 } from "uuid"

self.onmessage = async (event) => {
      const uploadStore = event.uploadStore
      const mainStore = event.mainStore
      let chunkSize = mainStore.user.maxDiscordMessageSize

      let totalSize = 0
      let attachments = []

      let queueFile
      while ((queueFile = uploadStore.getFileFromQueue())) {

            //CASE 1, file is > 25mb
            if (queueFile.fileObj.size > chunkSize) {
                  //CASE 1.1, attachments already created, we yield the already created attachments in a request
                  if (attachments.length !== 0) {
                        let request = { "totalSize": totalSize, "attachments": attachments }
                        totalSize = 0
                        attachments = []
                        postMessage(request)
                  }

                  //CASE 1.2 attachments are not created, we create chunked requests from the big file
                  let i = 0
                  for (let j = 0; j < queueFile.fileObj.size; j += chunkSize) {
                        let chunk = queueFile.systemFile.slice(j, j + chunkSize)

                        let attachment = { "type": attachmentType.chunked, "fileObj": queueFile.fileObj, "rawBlob": chunk, "fragmentSequence": i + 1 } //todo fragments shouldn't start at 1
                        attachments.push(attachment)
                        totalSize = totalSize + chunk.size

                        //CASE 1.2.1 chunk size is already 25mb, so we yield it in a request
                        if (totalSize === chunkSize) {
                              let request = { "totalSize": totalSize, "attachments": attachments }
                              totalSize = 0
                              attachments = []
                              postMessage(request)
                        }
                        i++
                  }
            }
            //CASE 2. file is < 25mb
            else {
                  //CASE 2.1 file is <25 mb but totalSize including fileObj.size is > 25mb or attachments.length == 10
                  //we need to yield the already created attachments in a request
                  if (totalSize + queueFile.systemFile.size > chunkSize || attachments.length === 10) {
                        let request = { "totalSize": totalSize, "attachments": attachments }
                        totalSize = 0
                        attachments = []
                        postMessage(request)
                  }

                  //CASE 2.2 file is < 25mb and attachments length < 10, and we can safely add it to attachments
                  let attachment = { "type": attachmentType.entireFile, "fileObj": queueFile.fileObj, "rawBlob": queueFile.systemFile, "fragmentSequence": 1 }
                  attachments.push(attachment)
                  totalSize = totalSize + queueFile.systemFile.size
            }

            //We now need to generate a thumbnail if needed.
            if (isVideoFile(queueFile)) {
                  let thumbnail = await getVideoCover(queueFile)

                  //CASE 1, totalSize including thumbnail.size is > 25mb or attachments.length == 10
                  if (totalSize + thumbnail.size > chunkSize || attachments.length === 10) {
                        let request = { "totalSize": totalSize, "attachments": attachments }
                        totalSize = 0
                        attachments = []
                        postMessage(request)

                  }

                  //we have to generate a new iv to not reuse the file one
                  let iv = generateThumbnailIv(queueFile.fileObj)
                  let attachment = { "type": attachmentType.thumbnail, "fileObj": queueFile.fileObj, "rawBlob": thumbnail, "iv": iv}
                  attachments.push(attachment)
                  totalSize = totalSize + thumbnail.size
            }

      }
      //we need to handle the already created attachments after break
      if (attachments.length > 0) {
            let request = { "totalSize": totalSize, "attachments": attachments, "id": uuidv4() }
            postMessage(request)

      }


}
