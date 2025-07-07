import { backendInstance } from "@/utils/networker.js"

export async function isPasswordCorrect(resourceId, password) {
   let url = `/resources/${resourceId}/password`
   try {
      let response = await backendInstance.head(url, {
         headers: {
            "Content-Type": "application/json",
            "X-resource-Password": password
         },
         __displayErrorToast: false
      })
      return response.status === 204
   } catch (e) {
      return false
   }
}
