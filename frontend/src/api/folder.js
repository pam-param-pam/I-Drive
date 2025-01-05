import {useMainStore} from "@/stores/mainStore.js"
import {backend_instance} from "@/utils/networker.js"

export async function getItems(folder_id, lockFrom) {
   const store = useMainStore()

   let url = "/folder/" + folder_id
   let password = store.getFolderPassword(lockFrom)

   let response = await backend_instance.get(url, {
      __cancelSignature: 'getItems',
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}

export async function getDirs(folder_id) {
   let url = "/folder/dirs/" + folder_id

   let response = await backend_instance.get(url)
   return response.data

}


export async function lockWithPassword(folder_id, password, oldPassword) {
   let url = `/folder/password/${folder_id}`
   let headers = {}

   if (oldPassword === "") {
      oldPassword = null
   } else {
      headers["X-resource-Password"] = encodeURIComponent(oldPassword)

   }
   if (password === "") {
      password = null
   }
   let data = {"new_password": password}
   let response = await backend_instance.post(url, data, {
      headers: headers,
      __manage469: false,
   })
   return response.data

}

export async function create(data) {
   let url = "/folder/create"
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function getUsage(folderId, lockFrom) {
   const store = useMainStore()

   let password = store.getFolderPassword(lockFrom)

   let url = `/folder/usage/${folderId}`
   let response = await backend_instance.get(url, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}

export async function resetPassword(folderId, accountPassword, newPassword) {
   let url = `/folder/password/reset/${folderId}`


   let data = {"accountPassword": accountPassword, "folderPassword": newPassword}
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function fetchAdditionalInfo(folderId) {

   let url = `/folder/moreinfo/${folderId}`
   let response = await backend_instance.get(url)
   return response.data

}