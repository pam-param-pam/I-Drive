import router from "@/router"
import { baseURL, baseWS } from "@/utils/constants"
import { getUser, logoutUser, registerUser } from "@/api/user.js"
import {useMainStore} from "@/stores/mainStore.js"
import app from "@/main.js"
import VueNativeSock from "vue-native-websocket-vue3"
import onEvent from "@/utils/WsEventhandler.js"


export async function validateLogin() { //this isn't really validate login - more like finish login xD
   const store = useMainStore()


   let token = localStorage.getItem("token")
   if (!token) {
      console.warn("TOKEN IS NULL ATEMPTED TO VALIDATE LOGIN")
      return
   }
   let body = await getUser(token)
   console.log("body")
   console.log(body)
   store.setUser(body.user)
   store.setSettings(body.settings)
   store.setPerms(body.perms)
   store.setToken(token)


   app.use(VueNativeSock, baseWS + "/user", {reconnection: false, protocol: token})
   app.config.globalProperties.$socket.onmessage = (data) => onEvent(data)

}

export async function login(username, password) {
   const data = {username, password}

   const res = await fetch(`${baseURL}/auth/token/login`, {
      method: "POST",
      headers: {
         "Content-Type": "application/json",
      },

      body: JSON.stringify(data),
   })

   const body = await res.text()

   if (res.status === 200) {

      const token = JSON.parse(body).auth_token

      localStorage.setItem("token", token)
      await validateLogin()

   } else {
      const error = new Error()
      error.status = res.status
      throw error
   }

}


export async function signup(username, password) {
   let data = {username, password}
   await registerUser(data)
   
}

export async function logout() {
   let store = useMainStore()

   let token = store.token
   store.setToken(null)
   localStorage.removeItem("token")

   if (token) {
      await logoutUser(token)
   }

   // store.setUser(null)
   // store.setSettings(null)
   // store.setCurrentFolder(null)
   // store.setItems(null)
   // store.setPerms(null)
   // store.resetFolderPassword()

   await router.push({path: "/login"})
   router.go(0) // make sure every state is removed just in case
}
