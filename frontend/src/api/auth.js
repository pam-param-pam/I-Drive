import { backendInstance } from "@/axios/networker.js"

export async function createQrSession() {
   let url = "/auth/qrcode"
   let response = await backendInstance.post(url, {}, {
      headers: {
         "Authorization": false
      }
   })
   return response.data
}


export async function changePassword(data) {
   let url = `/auth/password`
   let response = await backendInstance.patch(url, data)
   return response.data
}


export async function registerUser(data) {
   let url = "/auth/register"
   let response = await backendInstance.post(url, data, {
      headers: {
         "Authorization": false
      },
      __displayErrorToast: false
   })
   return response.data
}


export async function logoutUser(token) {
   let url = "/auth/token/logout"
   let response = await backendInstance.post(url, {}, {
      headers: {
         "Authorization": "token " + token
      }
   })
   return response.data
}


export async function getQrSessionDeviceInfo(sessionId) {
   let url = `/auth/qrcode/get/${sessionId}`
   let response = await backendInstance.get(url, {
      __displayErrorToast: false
   })
   return response.data
}


export async function closePendingQrSession(sessionId) {
   let url = `/auth/qrcode/cancel/${sessionId}`
   let response = await backendInstance.get(url, {
      __displayErrorToast: false
   })
   return response.data
}


export async function approveQrSession(sessionId) {
   let url = `/auth/qrcode/${sessionId}`
   let response = await backendInstance.post(url)
   return response.data
}


export async function getActiveDevices() {
   let url = `/auth/devices`
   let response = await backendInstance.get(url)
   return response.data
}


export async function revokeDevice(deviceId) {
   let url = `/auth/devices/${deviceId}`
   let response = await backendInstance.delete(url)
   return response.data
}


export async function logoutAllDevices() {
   let url = `/auth/devices/logout-all`
   let response = await backendInstance.post(url)
   return response.data
}


export async function loginUser(data) {
   let url = "/auth/token/login"
   let response = await backendInstance.post(url, data, {
      headers: {
         "Authorization": false
      },
      __displayErrorToast: false
   })
   return response.data
}