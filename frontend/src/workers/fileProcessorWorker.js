import { v4 as uuidv4 } from "uuid"
import { uploadType } from "@/utils/constants.js"
import { detectExtension } from "@/utils/common.js"
export function detectType(type, extension) {
   const RAW_IMAGE_EXTENSIONS = [
      ".IIQ", ".3FR", ".DCR", ".K25", ".KDC",
      ".CRW", ".CR2", ".CR3", ".ERF", ".MEF",
      ".MOS", ".NEF", ".NRW", ".ORF", ".PEF",
      ".RW2", ".ARW", ".SRF", ".SR2"
   ]
   if (RAW_IMAGE_EXTENSIONS.includes(extension.toUpperCase())) {
      return "image/raw"
   }
   else if (extension === ".mov") {
      return "video/mov"
   }
   else if (extension === ".mkv") {
      return "video/mkv"
   }
   else if (extension === ".ts") {
      return "video/ts"
   }
   else if (extension === ".avi") {
      return "video/avi"
   }
   else if (extension === ".mod") {
      return "text/plain"
   }
   if(!type) return "text/plain"
   return type

}

self.onmessage = async (event) => {

   let { typeOfUpload, folderContext, filesList, uploadId, encryptionMethod, parentPassword } = event.data
   let files = []

   for (let i = 0; i < filesList.length; i++) {
      let frontendId = uuidv4()
      let file
      let size
      let name
      let type
      let path
      let createdAt

      if (typeOfUpload === uploadType.dragAndDropInput) {
         file = filesList[i].file
         path = filesList[i].path
      } else if (typeOfUpload === uploadType.browserInput) {
         file = filesList[i]
         path = file.webkitRelativePath
      } else {
         console.error("convertUploadInput: invalid type: " + typeOfUpload)
      }

      size = file.size
      name = file.name
      createdAt = file.lastModified
      let extension = detectExtension(file.name)
      type = detectType(file.type, extension)
      // Remove filename from path if it exists at the end
      if (path && path.endsWith(file.name)) {
         path = path.slice(0, -file.name.length - 1)
      }

      let crc = 0
      files.push({ fileObj: { folderContext, uploadId, path, encryptionMethod, size, type, name, frontendId, createdAt, extension, parentPassword, crc }, "systemFile": file })
   }

   self.postMessage(files)


}
