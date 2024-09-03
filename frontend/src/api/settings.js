import {backend_instance} from "@/utils/networker.js"


export async function update(data) {
   let url = "/api/settings"
   let response = await backend_instance.put(url, data)
   return response.data

}
