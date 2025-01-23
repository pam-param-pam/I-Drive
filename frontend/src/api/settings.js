import {backendInstance} from "@/utils/networker.js"


export async function update(data) {
   let url = "/settings"
   let response = await backendInstance.put(url, data)
   return response.data

}
