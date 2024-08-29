import {useMainStore} from "@/stores/mainStore.js"
import {backend_instance} from "@/utils/networker.js"

export async function getFile(file_id, lockFrom) {
   const store = useMainStore()

   let url = `/api/file/${file_id}`
   let password = store.getFolderPassword(lockFrom)
   let response = await backend_instance.get(url, {
      headers: {
         "x-folder-password": password
      }
   })
   return response.data

}

export async function createThumbnail(data) {
   let url = `/api/file/thumbnail/create`
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function createFile(data) {
   let url = `/api/file/create`
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function patchFile(data) {
   let url = `/api/file/create`
   return await backend_instance.patch(url, data)

}
export async function getEncryptionSecrets(file_id) {
   let url = `/api/file/secrets/${file_id}`
   let response = await backend_instance.get(url)
   return response.data

}
export async function editFile(data) {
   let url = `/api/file/create`
   let response = await backend_instance.put(url, data)
   return response.data

}