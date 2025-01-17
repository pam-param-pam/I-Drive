import {backend_instance} from "@/utils/networker.js"

export async function getUser(token) {
   if (!token) return

   let url = "/user/me"
   let response = await backend_instance.get(url, {
      headers: {
         "Authorization": `Token ${token}`,
      }
   })
   return response.data

}
export async function registerUser(data) {
   let url = "/auth/register"
   let response = await backend_instance.post(url, data,{
      headers: {
         "Authorization": false,
      },
      __displayErrorToast: false
   })
   return response.data
}

export async function logoutUser(token) {
   let url = "/auth/token/logout"
   let response = await backend_instance.post(url, {}, {
      headers: {
         "Authorization": "token " + token,
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

export async function getDiscordSettings() {
   let url = `/user/discordSettings`
   let response = await backend_instance.get(url)
   return response.data
}

export async function addDiscordWebhook(data) {
   let url = `/user/discordSettings/webhook/add`
   let response = await backend_instance.post(url, data)
   return response.data
}

export async function deleteDiscordWebhook(data) {
   let url = `/user/discordSettings/webhook/delete`
   let response = await backend_instance.post(url, data)
   return response.data
}

export async function addDiscordBot(data) {
   let url = `/user/discordSettings/bot/add`
   let response = await backend_instance.post(url, data)
   return response.data
}

export async function deleteDiscordBot(data) {
   let url = `/user/discordSettings/bot/delete`
   let response = await backend_instance.post(url, data)
   return response.data
}

export async function updateDiscordSettings(data) {
   let url = `/user/updateDiscordSettings`
   let response = await backend_instance.put(url, data)
   return response.data
}

