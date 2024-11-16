import { v4 as uuidv4 } from "uuid"
import { uploadType } from "@/utils/constants.js"

self.onmessage = async (event) => {

   let {typeOfUpload, folderContext, filesList, uploadId, encryptionMethod} = event.data


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
      type = file.type
      createdAt = file.lastModified


      // Remove filename from path if it exists at the end
      if (path && path.endsWith(file.name)) {
         path = path.slice(0, -file.name.length - 1)
      }


      files.push({ fileObj: { folderContext, uploadId, path, encryptionMethod, size, type, name, frontendId, createdAt }, "systemFile": file })
   }

      console.log("files")
      console.log(files)
      self.postMessage(files)



}
