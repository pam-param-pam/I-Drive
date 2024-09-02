import {backend_instance} from "@/utils/networker.js";

export async function isPasswordCorrect(folder_id, password) {
   let url = `/api/resource/password/${folder_id}`
   let response = await backend_instance.get(url, {
      headers: {
         "Content-Type": "application/json",
         "X-resource-Password": password
      }
   })
   return response.status === 204
}
