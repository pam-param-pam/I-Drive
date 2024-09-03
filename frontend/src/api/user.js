import {useMainStore} from "@/stores/mainStore.js"
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
   let url = `/api/user/changepassword`
   let response = await backend_instance.post(url, data)
   return response.data


}

export async function updateSettings(data) {
   let url = `/api/user/updatesettings`
   await backend_instance.post(url, data)

}

export async function getTrash() {
   const store = useMainStore()

   let url = `/api/trash`
   store.setLoading(true)
   return backend_instance.get(url, {
      __cancelSignature: 'getItems',

   })
      .then(response => {
         store.setLoading(false)
         return response.data
      })
      .catch(error => {
         store.setLoading(error)
         throw error
      })
}



