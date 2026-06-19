import { v4 as uuidv4 } from "uuid"
import { detectExtension } from "@/utils/common.js"
import { uploadType } from "@/transfers/upload/constants.js"

const BATCH_SIZE = 1

let contexts = []
let currentCtxIndex = 0

self.onmessage = async (event) => {
   try {
      const msg = event.data

      if (msg.type === "reset") {
         contexts = []
         currentCtxIndex = 0
         return
      }

      if (msg.type === "init") {
         contexts.push({
            ...msg,
            index: 0
         })
         return
      }

      if (msg.type !== "produce") return

      let files = []

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

      self.postMessage({type: "newFiles", data: { files, done: currentCtxIndex >= contexts.length }})
   } catch (err) {
      self.postMessage({
         type: "crash",
         error: {
            name: err?.name ?? "Error",
            message: err?.message ?? String(err),
            stack: err?.stack ?? null
         }
      })
   }
}