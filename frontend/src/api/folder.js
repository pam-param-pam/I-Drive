import {useMainStore} from "@/stores/mainStore.js"
import {backendInstance} from "@/utils/networker.js"

export async function getItems(folderId, lockFrom) {
   const store = useMainStore()

   let url = `/folders/${folderId}`
   let password = store.getFolderPassword(lockFrom)

   let response = await backendInstance.get(url, {
      __cancelSignature: 'getItems',
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}

export async function getDirs(folderId) {
   let url = `/folders/${folderId}/dirs`

   let response = await backendInstance.get(url)
   return response.data

}


export async function lockWithPassword(folderId, password, oldPassword) {
   let url = `/folders/${folderId}/password`
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
   let response = await backendInstance.post(url, data, {
      headers: headers,
      __manage469: false,
   })
   return response.data

}

export async function create(data, config={}) {
   let url = "/folders"
   let response = await backendInstance.post(url, data, config)
   return response.data

}

export async function breadcrumbs(folderId) {
   let url = `/folders/${folderId}/breadcrumbs`
   let response = await backendInstance.get(url)
   return response.data
}

export async function getUsage(folderId, lockFrom) {
   const store = useMainStore()

   let password = store.getFolderPassword(lockFrom)

   let url = `/folders/${folderId}/usage`
   let response = await backendInstance.get(url, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}

export async function resetPassword(folderId, accountPassword, newPassword) {
   let url = `/folders/${folderId}/password/reset`

   let data = {"accountPassword": accountPassword, "folderPassword": newPassword}
   let response = await backendInstance.post(url, data)
   return response.data

}


export async function getFileStats(folderId) {
   let url = `/folders/${folderId}/stats`
   let response = await backendInstance.get(url)
   return response.data
}