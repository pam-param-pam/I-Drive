import { fetchURL, fetchJSON} from "./utils"

export async function getAllShares() {
  return fetchJSON("/api/shares", {})
}

export async function getShare(token, folderId= "") {
  let url = `/api/share/${token}`
  if (folderId.length > 0)
    url = `${url}/${folderId}`

  return fetchJSON(url, {}, false)
}

export async function removeShare(data) {
  await fetchURL(`/api/share/delete`, {
    method: "DELETE",
    body: JSON.stringify(data)

  })
}

export async function createShare(data) {
  return fetchJSON("/api/share/create", {
    method: "POST",
    body: JSON.stringify(data)
  })
}


