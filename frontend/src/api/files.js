import { useMainStore } from "@/stores/mainStore.js"
import { backendInstance } from "@/utils/networker.js"

export async function getFile(file_id, lockFrom) {
   const store = useMainStore()

   let url = `/file/${file_id}`
   let password = store.getFolderPassword(lockFrom)
   let response = await backendInstance.get(url, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}


export async function createThumbnail(data) {
   let url = `/file/thumbnail/create`
   let response = await backendInstance.post(url, data)
   return response.data
}


export async function createFile(data, password) {
   let url = `/file/create`
   let response = await backendInstance.post(url, data, {
      headers: {
         "x-resource-password": password
      },
      __retry500: true
   })
   return response.data

}


export async function editFile(data) {
   let url = `/file/create`
   let response = await backendInstance.put(url, data)
   return response.data

}


export async function updateVideoPosition(data, lockFrom) {
   let url = `/file/video/position`

   const store = useMainStore()
   let password = store.getFolderPassword(lockFrom)

   let response = await backendInstance.post(url, data, {
      headers: {
         "x-resource-password": password
      }
   })
   return response.data

}


export async function addTag(data) {
   let url = `/file/tag/add`
   let response = await backendInstance.post(url, data)
   return response.data

}


export async function removeTag(data) {
   let url = `/file/tag/remove`
   let response = await backendInstance.post(url, data)
   return response.data

}


export async function addMoment(data) {
   let url = `/file/moment/add`
   let response = await backendInstance.post(url, data)
   return response.data

}


export async function removeMoment(data) {
   let url = `/file/moment/remove`
   let response = await backendInstance.post(url, data)
   return response.data

}


export async function getMoments(file_id) {
   let url = `/file/moments/${file_id}`
   let response = await backendInstance.get(url)
   return response.data
}


export async function getTags(file_id) {
   let url = `/file/tags/${file_id}`
   let response = await backendInstance.get(url)
   return response.data
}


export async function removeSubtitle(data) {
   let url = `/file/subtitles/remove`
   let response = await backendInstance.post(url, data)
   return response.data
}


export async function addSubtitle(data) {
   let url = `/file/subtitles/add`
   let response = await backendInstance.post(url, data)
   return response.data
}


export async function getSubtitles(file_id) {
   let url = `/file/subtitles/${file_id}`
   let response = await backendInstance.get(url)
   return response.data
}

export async function getFileRawData(fileUrl, config = {}) {
   let response = await backendInstance.get(fileUrl, config)
   return response.data
}
