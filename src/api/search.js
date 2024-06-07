import {backend_instance} from "@/api/networker.js"

export async function search(argumentDict, source) {

  let queryParams = new URLSearchParams(argumentDict)

  let url = `/api/search?${queryParams.toString()}`
  let response = await backend_instance.get(url, {
    cancelToken: source.token
  })
  return response.data
}
