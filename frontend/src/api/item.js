import {backendInstance} from "@/utils/networker.js"

export async function moveToTrash(data) {
   let url = "/item/moveToTrash"
   let response = await backendInstance.patch(url, data)
   return response.data
}

export async function breadcrumbs(folder_id) {
   let url = `/folder/breadcrumbs/${folder_id}`
   let response = await backendInstance.get(url)
   return response.data
}

export async function restoreFromTrash(data) {
   let url = "/item/restoreFromTrash"
   let response = await backendInstance.patch(url, data)
   return response.data
}

export async function rename(data) {
   let url = "/item/rename"
   let response = await backendInstance.patch(url, data)
   return response.data
}

export async function move(data) {
   let url = "/item/move"
   let response = await backendInstance.patch(url, data)
   return response.data
}

export async function remove(data) {
   let url = "/item/delete"
   let response = await backendInstance.patch(url, data)
   return response.data
}

export async function createZIP(data) {
   let url = "/zip"
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function fetchAdditionalInfo(itemId) {
   let url = `/item/moreinfo/${itemId}`
   let response = await backendInstance.get(url)
   return response.data
}
