import { v4 as uuidv4 } from "uuid"
import { uploadType } from "@/utils/constants.js"
import { detectExtension } from "@/utils/common.js"

const BATCH_SIZE = 1

let contexts = []   // queue of upload contexts
let currentCtxIndex = 0

self.onmessage = async (event) => {
   const msg = event.data

   // INIT — append instead of overwrite
   if (msg.type === "init") {
      contexts.push({
         ...msg,
         index: 0
      })
      return
   }

   if (msg.type !== "produce") return

   let files = []
   let totalBytes = 0

   while (files.length < BATCH_SIZE && currentCtxIndex < contexts.length) {

      const ctx = contexts[currentCtxIndex]

      const {
         typeOfUpload,
         folderContext,
         filesList,
         uploadId,
         encryptionMethod,
         parentPassword,
         lockFrom
      } = ctx

      // If this context is exhausted → move to next
      if (ctx.index >= filesList.length) {
         currentCtxIndex++
         continue
      }

      let frontendId = uuidv4()
      let file
      let path

      if (typeOfUpload === uploadType.dragAndDropInput) {
         file = filesList[ctx.index].file
         path = filesList[ctx.index].path
      } else if (typeOfUpload === uploadType.browserInput) {
         file = filesList[ctx.index]
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

      ctx.index++
   }

   self.postMessage({
      files,
      totalBytes,
      done: currentCtxIndex >= contexts.length
   })
}