import {backend_instance} from "@/utils/networker.js"

export async function getUser(token) {
   if (!token) return

   let url = "/auth/user/me"
   let response = await backend_instance.get(url, {
      headers: {
         "Authorization": `Token ${token}`,
      }
   })
   return response.data

}

export async function changePassword(data) {
   let url = `/user/changepassword`
   let response = await backend_instance.post(url, data)
   return response.data


}

export async function updateSettings(data) {
   let url = `/user/updatesettings`
   await backend_instance.post(url, data)

}

export async function getTrash() {
   let url = `/trash`
   let response = await backend_instance.get(url, {
      __cancelSignature: 'getItems',

   })
   return response.data

}



