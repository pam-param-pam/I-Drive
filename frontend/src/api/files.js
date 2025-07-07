import { useMainStore } from "@/stores/mainStore.js"
import { backendInstance } from "@/utils/networker.js"

export async function getFile(fileId, lockFrom) {
   const store = useMainStore()

   let url = `/files/${fileId}`
   let password = store.getFolderPassword(lockFrom)
   let response = await backendInstance.get(url, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}


export async function createThumbnail(fileId, data) {
   let url = `/files/${fileId}/thumbnail`
   let response = await backendInstance.post(url, data)
   return response.data
}


export async function createFile(data, password) {
   let url = `/files`
   let response = await backendInstance.post(url, data, {
      headers: {
         "x-resource-password": password
      },
      __retry500: true
   })
   return response.data

}


export async function editFile(fileId, data) {
   let url = `/files/${fileId}`
   let response = await backendInstance.put(url, data)
   return response.data

}


export async function updateVideoPosition(fileId, lockFrom, data) {
   let url = `/files/${fileId}/video-position`

   const store = useMainStore()
   let password = store.getFolderPassword(lockFrom)

   let response = await backendInstance.put(url, data, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}


export async function addTag(fileId, data) {
   let url = `/files/${fileId}/tag`
   let response = await backendInstance.post(url, data)
   return response.data

}


export async function removeTag(fileId, data) {
   let url = `/files/${fileId}/tag`
   let response = await backendInstance.delete(url, data)
   return response.data

}


export async function addMoment(fileId, data) {
   let url = `/files/${fileId}/moments`
   let response = await backendInstance.post(url, data)
   return response.data

}


export async function removeMoment(fileId, timestamp) {
   let url = `/files/${fileId}/moments/${timestamp}`
   let response = await backendInstance.delete(url)
   return response.data

}


export async function getMoments(fileId) {
   let url = `/files/${fileId}/moments`
   let response = await backendInstance.get(url)
   return response.data
}


export async function getTags(fileId) {
   let url = `/files/${fileId}/tags`
   let response = await backendInstance.get(url)
   return response.data
}


export async function getSubtitles(fileId) {
   const url = `/files/${fileId}/subtitles`
   const response = await backendInstance.get(url)
   return response.data
}

export async function addSubtitle(fileId, data) {
   const url = `/files/${fileId}/subtitles`
   const response = await backendInstance.post(url, data)
   return response.data
}

export async function deleteSubtitle(fileId, subtitleId) {
   const url = `/files/${fileId}/subtitles/${subtitleId}`
   const response = await backendInstance.delete(url)
   return response.data
}

export async function getFileRawData(fileUrl, config = {}) {
   let response = await backendInstance.get(fileUrl, config)
   return response.data
}
