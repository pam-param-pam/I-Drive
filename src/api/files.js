import {backend_instance} from "@/api/networker.js"

export async function getFile(file_id) {
  let url = `/api/file/${file_id}`
  let response = await backend_instance.get(url)
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