import {backend_instance} from "@/api/networker.js"
import store from "@/store/index.js";

export async function getFile(file_id, lockFrom) {
  let url = `/api/file/${file_id}`
  let password = store.getters.getFolderPassword(lockFrom)
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
  let response = await backend_instance.patch(url, data)
  return response.data

}