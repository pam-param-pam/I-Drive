import { backendInstance } from "@/axios/networker.js"

export async function moveToTrash(data) {
   let url = `/items/moveToTrash`
   let response = await backendInstance.patch(url, data)
   return response.data
}


export async function restoreFromTrash(data) {
   let url = `/items/restoreFromTrash`
   let response = await backendInstance.patch(url, data)
   return response.data
}


export async function move(data) {
   let url = `/items/move`
   let response = await backendInstance.patch(url, data)
   return response.data
}


export async function remove(data) {
   let url = `/items/delete`
   let response = await backendInstance.post(url, data)
   return response.data
}


export async function createZIP(data) {
   let url = `items/zip`
   let response = await backendInstance.post(url, data)
   return response.data
}


export async function rename(itemId, data) {
   let url = `/items/${itemId}/rename`
   let response = await backendInstance.patch(url, data)
   return response.data
}


export async function fetchAdditionalInfo(itemId) {
   let url = `/items/${itemId}/moreinfo`
   let response = await backendInstance.get(url)
   return response.data
}


export async function isPasswordCorrect(itemId, password) {
   let url = `/items/${itemId}/password`
   try {
      let response = await backendInstance.get(url, {
         headers: {
            "X-resource-Password": password
         }
      })
      return response.status === 204
   } catch (e) {
      return false
   }
}