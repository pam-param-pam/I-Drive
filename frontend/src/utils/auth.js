import router from "@/router"
import {baseURL} from "@/utils/constants"
import {getUser} from "@/api/user.js"
import {useMainStore} from "@/stores/mainStore.js"


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

   //await openWebsocket(token)

   console.log(store.user)

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
   const data = {username, password}

   const res = await fetch(`${baseURL}/api/signup`, {
      method: "POST",
      headers: {
         "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
   })

   if (res.status !== 200) {
      throw new Error(res.status)
   }
}

export async function logout() {
   const store = useMainStore()


   let token = store.token
   if (token) {
      const res = await fetch(`${baseURL}/auth/token/logout`, {
         method: "POST",
         headers: {
            "Authorization": `Token ${token}`,
         },

      })
   }


   store.setUser(null)
   store.setSettings(null)
   store.setToken(null)
   store.setCurrentFolder(null)
   store.setItems(null)
   store.setPerms(null)
   store.resetFolderPassword()

   localStorage.removeItem("token")
   await router.push({path: "/login"})
   router.go(0) // make sure every state is removed just in case
}
