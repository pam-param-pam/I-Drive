import {useMainStore} from "@/stores/mainStore.js"
import {backend_instance} from "@/utils/networker.js"

export async function getFile(file_id, lockFrom) {
   const store = useMainStore()

   let url = `/file/${file_id}`
   let password = store.getFolderPassword(lockFrom)
   let response = await backend_instance.get(url, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}

export async function createThumbnail(data) {
   let url = `/file/thumbnail/create`
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function createFile(data) {
   let url = `/file/create`
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function patchFile(data) {
   let url = `/file/create`
   return await backend_instance.patch(url, data)

}
export async function getEncryptionSecrets(file_id) {
   let url = `/file/secrets/${file_id}`
   let response = await backend_instance.get(url)
   return response.data

}
export async function editFile(data) {
   let url = `/file/create`
   let response = await backend_instance.put(url, data)
   return response.data

}

export async function updateVideoPosition(data) {
   let url = `/file/video/position`
   let response = await backend_instance.post(url, data)
   return response.data

}