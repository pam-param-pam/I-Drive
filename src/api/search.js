import {backend_instance} from "@/api/networker.js"

export async function search(argumentDict, lockFrom=null, password=null) {
  let headers = {}
  if (lockFrom && password) {
    argumentDict["lockFrom"] = lockFrom
    headers["X-Folder-Password"] = password
  }
  let queryParams = new URLSearchParams(argumentDict)

  let url = `/api/search?${queryParams.toString()}`


  let response = await backend_instance.get(url, {
    __cancelSignature: 'getItems',
    headers: headers
  })
  return response.data
}
