import {backendInstance} from "@/utils/networker.js"
import {useMainStore} from "@/stores/mainStore.js";

export async function getAllShares() {
   let url = "/shares"
   let response = await backendInstance.get(url)
   return response.data
}

export async function getShare(token, folderId = "") {
   let url = `/share/${token}`
   if (folderId) url = url + `/${folderId}`


   let response = await backendInstance.get(url, {
      headers: {
         "Authorization": false,
      }
   })
   return response.data
}

export async function removeShare(data) {
   let url = "/share/delete"
   let response = await backendInstance.patch(url, data)
   return response.data

}

export async function createShare(data) {
   let url = "/share/create"
   let response = await backendInstance.post(url, data)
   return response.data

}

export async function createShareZIP(token, data) {
   let url = "/share/zip/" + token
   let response = await backendInstance.post(url, data)
   return response.data
}
