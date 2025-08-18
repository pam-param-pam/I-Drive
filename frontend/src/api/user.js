import {backendInstance} from "@/utils/networker.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { useToast } from "vue-toastification"
import i18n from "@/i18n/index.js"

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

export async function loginUser(data) {
   let url = "/auth/token/login"
   let response = await backendInstance.post(url, data,{
      headers: {
         "Authorization": false,
      },
      __displayErrorToast: false
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
   let url = `/user/password`
   let response = await backendInstance.patch(url, data)
   return response.data


}

export async function updateSettings(data) {
   let url = `/user/settings`
   await backendInstance.put(url, data)

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
   let url = `/user/discordSettings/webhooks`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function deleteDiscordWebhook(discordId) {
   let url = `/user/discordSettings/webhooks/${discordId}`
   let response = await backendInstance.delete(url)
   return response.data
}

export async function addDiscordBot(data) {
   let url = `/user/discordSettings/bots`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function deleteDiscordBot(discordId) {
   let url = `/user/discordSettings/bots/${discordId}`
   let response = await backendInstance.delete(url)
   return response.data
}

export async function updateDiscordSettings(data) {
   let url = `/user/discordSettings`
   let response = await backendInstance.patch(url, data)
   return response.data
}

export async function canUpload(folderContext) {
   let url = `/user/canUpload/${folderContext}`
   let response = await backendInstance.get(url)
   if (response.data.can_upload) {
      let uploadStore = useUploadStore()
      uploadStore.setWebhooks(response.data.webhooks)
      uploadStore.setAttachmentName(response.data.attachment_name)
      uploadStore.setFileExtensions(response.data.extensions)

   }
   else {
      let toast = useToast()
      toast.error(i18n.global.t("errors.notAllowedToUpload"), {timeout: null})
   }
   return response.data
}

export async function autoSetup(data) {
   let url = `/user/discordSettings/autoSetup`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function deleteDiscordSettings() {
   let url = `/user/discordSettings`
   let response = await backendInstance.delete(url)
   return response.data
}

export async function getActiveDevices() {
   let url = `/user/devices`
   let response = await backendInstance.get(url)
   return response.data
}

export async function revokeDevice(deviceId) {
   let url = `/user/devices/${deviceId}`
   let response = await backendInstance.delete(url)
   return response.data
}

export async function logoutAllDevices() {
   let url = `/user/devices/logout-all`
   let response = await backendInstance.post(url)
   return response.data
}
