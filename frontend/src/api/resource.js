import { backendInstance } from "@/utils/networker.js"

export async function isPasswordCorrect(resourceId, password) {
   let url = `/resources/${resourceId}/password`
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
