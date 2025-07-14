import { backendInstance } from "@/utils/networker.js"

export async function isPasswordCorrect(itemId, password) {
   let url = `/items/${itemId}/password`
   try {
      let response = await backendInstance.get(url, {
         headers: {
            "X-resource-Password": password
         },
      })
      return response.status === 204
   } catch (e) {
      return false
   }
}
