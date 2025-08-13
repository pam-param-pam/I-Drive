import router from "@/router"
import { baseURL, baseWS } from "@/utils/constants"
import { getUser, loginUser, logoutUser, registerUser } from "@/api/user.js"
import { useMainStore } from "@/stores/mainStore.js"
import app from "@/main.js"
import VueNativeSock from "vue-native-websocket-vue3"
import { onEvent } from "@/utils/WsEventhandler.js"


export async function validateLogin() { //this isn't really validate login - more like finish login xD
   let mainStore = useMainStore()

   let token = localStorage.getItem("token")
   if (!token) {
      console.warn("TOKEN IS NULL ATTEMPTED TO VALIDATE LOGIN")
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

function saveAuth(data) {
   let token = data.auth_token
   let deviceId = data.device_id
   if (!token || !deviceId) {
      console.error("DEVICE_ID or TOKEN is null")
   }
   localStorage.setItem("token", token)
   localStorage.setItem("device_id", deviceId)
}

export async function login(username, password) {
   let data = await loginUser({ username, password })
   saveAuth(data)
   await validateLogin()
}


export async function signup(username, password) {
   let data = await registerUser({ username, password })
   saveAuth(data)
   await validateLogin()
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



