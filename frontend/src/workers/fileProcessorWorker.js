import { v4 as uuidv4 } from "uuid"
import { uploadType } from "@/utils/constants.js"
import { detectExtension } from "@/utils/common.js"

let ctx = null
let index = 0
const BATCH_SIZE = 1

self.onmessage = async (event) => {
   const msg = event.data

   // one-time init
   if (msg.type === "init") {
      ctx = msg
      index = 0
      return
   }

   if (msg.type !== "produce") return

   const {
      typeOfUpload,
      folderContext,
      filesList,
      uploadId,
      encryptionMethod,
      parentPassword,
      lockFrom
   } = ctx

   let files = []
   let totalBytes = 0

   while (files.length < BATCH_SIZE && index < filesList.length) {
      let frontendId = uuidv4()
      let file
      let path

      if (typeOfUpload === uploadType.dragAndDropInput) {
         file = filesList[index].file
         path = filesList[index].path
      } else if (typeOfUpload === uploadType.browserInput) {
         file = filesList[index]
         path = file.webkitRelativePath
      } else {
         throw new Error("invalid upload type")
      }

      const size = file.size
      const name = file.name
      const createdAt = file.lastModified
      const extension = detectExtension(name)

      if (path && path.endsWith(name)) {
         path = path.slice(0, -name.length - 1)
      }

      totalBytes += size

      files.push({
         fileObj: {
            folderContext,
            uploadId,
            path,
            encryptionMethod,
            size,
            name,
            frontendId,
            createdAt,
            extension,
            parentPassword,
            lockFrom,
            crc: 0
         },
         systemFile: file
      })

      index++
   }

   self.postMessage({
      files,
      totalBytes,
      done: index >= filesList.length
   })
}
