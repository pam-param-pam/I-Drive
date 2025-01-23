import {backendInstance} from "@/utils/networker.js";

export async function isPasswordCorrect(folder_id, password) {
   let url = `/resource/password/${folder_id}`
   let response = await backendInstance.get(url, {
      headers: {
         "Content-Type": "application/json",
         "X-resource-Password": password
      }
   })
   return response.status === 204
}
