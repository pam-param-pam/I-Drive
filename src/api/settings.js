import {backend_instance} from "@/api/networker.js"



export async function update(data) {
  let url = "/api/settings"
  let response = await backend_instance.put(url, data)
  return response.data

}
