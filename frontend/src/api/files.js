import {useMainStore} from "@/stores/mainStore.js"
import {backendInstance} from "@/utils/networker.js"

export async function getFile(file_id, lockFrom) {
   const store = useMainStore()

   let url = `/file/${file_id}`
   let password = store.getFolderPassword(lockFrom)
   let response = await backendInstance.get(url, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}

export async function createThumbnail(data) {
   let url = `/file/thumbnail/create`
   let response = await backendInstance.post(url, data, {
      __retry500: true,
   })
   return response.data

}

export async function createFile(data) {
   let url = `/file/create`
   let response = await backendInstance.post(url, data, {
      __retry500: true,
   })
   return response.data

}

export async function patchFile(data) {
   let url = `/file/create`
   let response = await backendInstance.patch(url, data, {
      __retry500: true,
   })
   return response.data
}
export async function getEncryptionSecrets(file_id) {
   let url = `/file/secrets/${file_id}`
   let response = await backendInstance.get(url)
   return response.data

}
export async function editFile(data) {
   let url = `/file/create`
   let response = await backendInstance.put(url, data)
   return response.data

}

export async function updateVideoPosition(data) {
   let url = `/file/video/position`
   let response = await backendInstance.post(url, data)
   return response.data

}

export async function addTag(data) {
   let url = `/file/tag/add`
   let response = await backendInstance.post(url, data)
   return response.data

}

export async function removeTag(data) {
   let url = `/file/tag/remove`
   let response = await backendInstance.post(url, data)
   return response.data

}