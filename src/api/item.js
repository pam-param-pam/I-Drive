import {backend_instance} from "@/utils/networker.js"

export async function moveToTrash(data) {
   let url = "/api/item/moveToTrash"
   return await backend_instance.patch(url, data)
}

export async function breadcrumbs(folder_id) {
   let url = `/api/folder/breadcrumbs/${folder_id}`
   let response = await backend_instance.get(url)
   return response.data
}

export async function restoreFromTrash(data) {
   let url = "/api/item/restoreFromTrash"
   return await backend_instance.patch(url, data)
}

export async function rename(data) {
   let url = "/api/item/rename"
   let response = await backend_instance.patch(url, data)
   return response.data
}

export async function move(data) {
   let url = "/api/item/move"
   let response = await backend_instance.patch(url, data)
   return response.data
}

export async function remove(data) {
   let url = "/api/item/delete"
   let response = await backend_instance.patch(url, data)
   return response.data
}

export async function createZIP(data) {
   let url = "/api/zip"
   let response = await backend_instance.post(url, data)
   return response.data
}

