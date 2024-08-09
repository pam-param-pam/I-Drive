import {backend_instance} from "@/api/networker.js"
import store from "@/store/index.js"

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
  let response = await backend_instance.post(url, data)
  return response.data


}

export async function updateSettings(data) {
  let url = `/api/user/updatesettings`
  await backend_instance.post(url, data)

}

export async function getTrash() {
  let url = `/api/trash`
  store.commit("setLoading", true)

  return backend_instance.get(url, {
    __cancelSignature: 'getItems',

  })
    .then(response => {
      store.commit("setLoading", false)
      return response.data
    })
    .catch(error => {
      store.commit("setError", error)
      throw error
    })
}



