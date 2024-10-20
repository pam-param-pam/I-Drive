import {backend_instance} from "@/utils/networker.js"
import {useMainStore} from "@/stores/mainStore.js";

export async function getAllShares() {
   let url = "/shares"
   let response = await backend_instance.get(url)
   return response.data
}

export async function getShare(token, folderId = "") {
   let url = `/share/${token}`
   if (folderId) url = url + `/${folderId}`


   let response = await backend_instance.get(url, {
      headers: {
         "Authorization": false,
      }
   })
   return response.data
}

export async function removeShare(data) {
   let url = "/share/delete"
   let response = await backend_instance.patch(url, data)
   return response.data

}

export async function createShare(data) {
   let url = "/share/create"
   let response = await backend_instance.post(url, data)
   return response.data

}


