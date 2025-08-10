import router from "@/router"
import { baseURL, baseWS } from "@/utils/constants"
import { getUser, logoutUser, registerUser } from "@/api/user.js"
import { useMainStore } from "@/stores/mainStore.js"
import app from "@/main.js"
import VueNativeSock from "vue-native-websocket-vue3"
import { onEvent } from "@/utils/WsEventhandler.js"


export async function validateLogin() { //this isn't really validate login - more like finish login xD
   const mainStore = useMainStore()


   let token = localStorage.getItem("token")
   if (!token) {
      console.warn("TOKEN IS NULL ATEMPTED TO VALIDATE LOGIN")
      return
   }
   let body = await getUser(token)

   mainStore.setUser(body.user)
   mainStore.setSettings(body.settings)
   mainStore.setPerms(body.perms)
   mainStore.setToken(token)
   mainStore.setTheme(body.settings.theme)

   app.use(VueNativeSock, baseWS + "/user", { reconnection: false, protocol: token })
   app.config.globalProperties.$socket.onmessage = (data) => onEvent(data).then()

}


export async function login(username, password) {
   let data = { username, password }

   let res = await fetch(`${baseURL}/auth/token/login`, {
      method: "POST",
      headers: {
         "Content-Type": "application/json"
      },

      body: JSON.stringify(data)
   })

   let body = await res.text()

   if (res.status === 200) {

      let token = JSON.parse(body).auth_token
      let deviceId = JSON.parse(body).device_id

      localStorage.setItem("token", token)
      localStorage.setItem("device_id", deviceId)

      await validateLogin()

   } else {
      const error = new Error()
      // Map status and headers to from fetch to look the same way as axios ones
      error.status = res.status
      error.response = {}
      let headers = {}
      res.headers.forEach((value, key) => {
         headers[key] = value
      })
      error.response.headers = headers
      throw error
   }

}


export async function signup(username, password) {
   let data = { username, password }
   await registerUser(data)

}


export async function logout() {
   console.log("POLITE LOGOUT ACKNOWLEDGED")

   let store = useMainStore()

   let token = store.token
   store.setToken(null)
   localStorage.removeItem("token")
   localStorage.removeItem("device_id")

   if (token) {
      await logoutUser(token)
   }

   await router.push({ path: "/login" })
   router.go(0) // make sure every state is removed just in case
}
export async function forceLogout() {
   console.log("FORCE LOGOUT ACKNOWLEDGED")
   localStorage.removeItem("token")
   await router.push({ path: "/login" })
   router.go(0)
}



