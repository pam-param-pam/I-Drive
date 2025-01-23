import {backendInstance} from "@/utils/networker.js"

export async function getUser(token) {
   if (!token) return

   let url = "/user/me"
   let response = await backendInstance.get(url, {
      headers: {
         "Authorization": `Token ${token}`,
      }
   })
   return response.data

}
export async function registerUser(data) {
   let url = "/auth/register"
   let response = await backendInstance.post(url, data,{
      headers: {
         "Authorization": false,
      },
      __displayErrorToast: false
   })
   return response.data
}

export async function logoutUser(token) {
   let url = "/auth/token/logout"
   let response = await backendInstance.post(url, {}, {
      headers: {
         "Authorization": "token " + token,
      }
   })
   return response.data
}

export async function changePassword(data) {
   let url = `/user/changepassword`
   let response = await backendInstance.post(url, data)
   return response.data


}

export async function updateSettings(data) {
   let url = `/user/updatesettings`
   await backendInstance.post(url, data)

}

export async function getTrash() {
   let url = `/trash`
   let response = await backendInstance.get(url, {
      __cancelSignature: 'getItems',

   })
   return response.data

}

export async function getDiscordSettings() {
   let url = `/user/discordSettings`
   let response = await backendInstance.get(url)
   return response.data
}

export async function addDiscordWebhook(data) {
   let url = `/user/discordSettings/webhook/add`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function deleteDiscordWebhook(data) {
   let url = `/user/discordSettings/webhook/delete`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function addDiscordBot(data) {
   let url = `/user/discordSettings/bot/add`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function deleteDiscordBot(data) {
   let url = `/user/discordSettings/bot/delete`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function updateDiscordSettings(data) {
   let url = `/user/updateDiscordSettings`
   let response = await backendInstance.put(url, data)
   return response.data
}

export async function enableDiscordBot(data) {
   let url = `/user/discordSettings/bot/enable`
   let response = await backendInstance.post(url, data)
   return response.data
}
