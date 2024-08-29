import {useMainStore} from "@/stores/mainStore.js"
import {backend_instance} from "@/utils/networker.js"

export async function getItems(folder_id, lockFrom) {
   const store = useMainStore()

   let url = "/api/folder/" + folder_id
   let password = store.getFolderPassword(lockFrom)
   store.setLoading(true)

   return backend_instance.get(url, {
      __cancelSignature: 'getItems',
      headers: {
         "x-folder-password": password
      }
   })
      .then(response => {
         store.setLoading(false)
         console.log("seting loading false")
         return response.data
      })
      .catch(error => {
         store.setError(error)
         throw error
      })
}

export async function getDirs(folder_id) {
   let url = "/api/folder/dirs/" + folder_id

   let response = await backend_instance.get(url)
   return response.data

}


export async function lockWithPassword(folder_id, password, oldPassword) {
   let url = `/api/folder/password/${folder_id}`
   let headers = {}

   if (oldPassword === "") {
      oldPassword = null
   } else {
      headers["X-Folder-Password"] = encodeURIComponent(oldPassword)

   }
   if (password === "") {
      password = null
   }
   let data = {"new_password": password}
   let response = await backend_instance.post(url, data, {
      headers: headers
   })
   return response.data

}

export async function create(data) {
   let url = "/api/folder/create"
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function getUsage(folderId, lockFrom) {
   const store = useMainStore()

   let password = store.getFolderPassword(lockFrom)

   let url = `/api/folder/usage/${folderId}`
   let response = await backend_instance.get(url, {
      headers: {
         "x-folder-password": password
      }
   })
   return response.data

}

export async function resetPassword(folderId, accountPassword, newPassword) {
   let url = `/api/folder/password/reset/${folderId}`


   let data = {"accountPassword": accountPassword, "folderPassword": newPassword}
   let response = await backend_instance.post(url, data)
   return response.data

}

export async function fetchAdditionalInfo(folderId) {

   let url = `/api/folder/moreinfo/${folderId}`
   let response = await backend_instance.get(url)
   return response.data

}