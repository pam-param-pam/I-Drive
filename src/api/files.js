import {fetchJSON} from "@/api/utils.js"

export async function getFile(file_id) {

  return await fetchJSON(`/api/file/${file_id}`, {

  })
}

export async function createThumbnail(data) {

  return await fetchJSON(`/api/file/thumbnail/create`, {
    method: "POST",
    body: JSON.stringify(data)
  })
}
