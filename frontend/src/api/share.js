import { backendInstance } from "@/utils/networker.js"

export async function getAllShares() {
   let url = "/shares"
   let response = await backendInstance.get(url)
   return response.data
}

export async function getShare(token, folderId = "") {
   let url = `/shares/${token}`
   if (folderId) url = url + `/folders/${folderId}`


   let response = await backendInstance.get(url, {
      headers: {
         "Authorization": false,
      },
      __shareContext: true

   })
   return response.data
}

export async function deleteShare(token) {
   let url = `/shares/${token}`
   let response = await backendInstance.delete(url)
   return response.data
}

export async function createShare(data) {
   let url = `/shares`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function createShareZIP(token, data) {
   let url = `/shares/${token}/zip`
   let response = await backendInstance.post(url, data)
   return response.data
}

export async function getShareSubtitles(token, fileId) {
   let url = `/shares/${token}/files/${fileId}/subtitles`
   let response = await backendInstance.get(url)
   return response.data
}


export async function isSharePasswordCorrect(token, password) {
   let url = `/shares/${token}/password`
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