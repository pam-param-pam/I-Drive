import {backend_instance} from "@/api/networker.js"

export async function search(argumentDict) {
  let queryParams = new URLSearchParams(argumentDict)

  let url = `/api/search?${queryParams.toString()}`
  let response = await backend_instance.get(url)
  return response.data
}
