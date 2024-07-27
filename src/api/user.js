import {backend_instance} from "@/api/networker.js"

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
  let url = `/api/user/changepassword`
  await backend_instance.post(url, data)

}

export async function updateSettings(data) {
  let url = `/api/user/updatesettings`
  await backend_instance.post(url, data)

}

export async function getTrash() {
  let url = `/api/trash`
  let response = await backend_instance.get(url, {
    __cancelSignature: 'getItems',
  })
  return response.data
}



