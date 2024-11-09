import { v4 as uuidv4 } from "uuid"
import { uploadType } from "@/utils/constants.js"

self.onmessage = async (event) => {

   let {typeOfUpload, folderContext, filesList, uploadId, encryptionMethod} = event.data

   let files = []

   for (let i = 0; i < filesList.length; i++) {
      let file = filesList[i]
      let size = file.size
      let name = file.name
      let type = file.type
      let frontendId = uuidv4()
      console.log("typeOfUpload")
      console.log(typeOfUpload)

      let path
      if (typeOfUpload === uploadType.browserInput) {
         path = file.webkitRelativePath
      } else if (typeOfUpload === uploadType.dragAndDropInput) {
         path = file.path
      } else {
         console.error("convertUploadInput: invalid type: " + typeOfUpload)
      }

      // Remove filename from path if it exists at the end
      if (path && path.endsWith(file.name)) {
         path = path.slice(0, -file.name.length - 1)
      }
      console.log(file)
      console.log("path")
      console.log(path)

      files.push({ fileObj: { folderContext, uploadId, path, encryptionMethod, size, type, name, frontendId }, "systemFile": file })
   }

   console.log("files")
   console.log(files)
   return files

}
