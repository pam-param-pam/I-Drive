import { backendInstance } from "@/axios/networker.js"

export async function search(argumentDict, lockFrom = null, password = null) {
   let headers = {}
   if (password) {
      headers["X-resource-Password"] = password
   }

   // Build the request body (the filter object)
   const body = { ...argumentDict }
   if (lockFrom) {
      body.lockFrom = lockFrom
   }

   const url = `/user/search`
   const response = await backendInstance.post(url, body, {
      __cancelSignature: "getItems",
      headers: headers
   })
   return response.data
}
