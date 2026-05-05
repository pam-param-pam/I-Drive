import { backendInstance } from "@/axios/networker.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { showToast } from "@/utils/common.js"

export async function getUser(token) {
   if (!token) return

   let url = "/user/me"
   let response = await backendInstance.get(url, {
      headers: {
         "Authorization": `Token ${token}`
      }
   })
   return response.data
}

export async function checkWifi() {
   let url = "/healthcheck/"
   let response = await backendInstance.get(url, {
      headers: {
         "Authorization": false
      },
      __displayErrorToast: false

   })
   return response.data
}



export async function updateSettings(data) {
   let url = `/user/settings`
   await backendInstance.put(url, data)

}


export async function getTrash() {
   let url = `/trash`
   let response = await backendInstance.get(url, {
      __cancelSignature: "getItems"

   })
   return response.data
}


export async function getDiscordSettings() {
   let url = `/user/discord-settings`
   let response = await backendInstance.get(url)
   return response.data
}


export async function createWebhooks() {
   let url = `/user/discord-settings/create-webhooks`
   let response = await backendInstance.post(url)
   return response.data
}


export async function deleteDiscordWebhook(discordId) {
   let url = `/user/discord-settings/webhooks/${discordId}`
   let response = await backendInstance.delete(url)
   return response.data
}


export async function addDiscordBot(data) {
   let url = `/user/discord-settings/bots`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function reenableCredential(discordId) {
   let url = `/user/discord-settings/credentials/${discordId}/enable`
   let response = await backendInstance.post(url)
   return response.data
}

export async function deleteDiscordBot(discordId) {
   let url = `/user/discord-settings/bots/${discordId}`
   let response = await backendInstance.delete(url)
   return response.data
}


export async function updateDiscordSettings(data) {
   let url = `/user/discord-settings`
   let response = await backendInstance.patch(url, data)
   return response.data
}


export async function canUpload(folderContext) {
   let url = `/user/can-upload/${folderContext}`
   let response = await backendInstance.get(url)
   if (response.data.can_upload) {
      let uploadStore = useUploadStore()
      uploadStore.setWebhooks(response.data.webhooks)
      uploadStore.setAttachmentName(response.data.attachment_name)
      uploadStore.setFileExtensions(response.data.extensions)
      return response.data
   } else {
      showToast("error", "errors.notAllowedToUpload", { timeout: null })
      return response.data
   }
}


export async function autoSetup(data) {
   let url = `/user/discord-settings/setup`
   let response = await backendInstance.post(url, data)
   return response.data
}


export async function deleteDiscordSettings() {
   let url = `/user/discord-settings`
   let response = await backendInstance.delete(url)
   return response.data
}


export async function getNotifications(more) {
   let url = `/user/notifications?more=${more}`
   let response = await backendInstance.get(url)
   return response.data
}

export async function setNotificationsStatus(data) {
   let url = `/user/notifications`
   let response = await backendInstance.post(url, data)
   return response.data
}
