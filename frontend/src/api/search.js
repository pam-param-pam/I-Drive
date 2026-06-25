import { backendInstance } from "@/axios/networker.js"

export async function search(argumentDict, lockFrom = null, password = null) {
   const body = { ...argumentDict }
   if (lockFrom && password) {
      body.lockFrom = lockFrom
      body.password = password
   }

   const url = `/user/search`
   const response = await backendInstance.post(url, body, {
      __cancelSignature: ["getItems", "search"],
   })
   return response.data
}
