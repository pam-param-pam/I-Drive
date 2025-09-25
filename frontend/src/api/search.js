import {backendInstance} from "@/axios/networker.js"

export async function search(argumentDict, lockFrom = null, password = null) {
   let headers = {}
   if (lockFrom && password) {
      argumentDict["lockFrom"] = lockFrom
      headers["X-resource-Password"] = password
   }
   let queryParams = new URLSearchParams(argumentDict)

   let url = `/search?${queryParams.toString()}`


   let response = await backendInstance.get(url, {
      __cancelSignature: 'getItems',
      headers: headers
   })
   return response.data
}
