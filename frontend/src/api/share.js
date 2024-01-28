import { fetchURL, fetchJSON, removePrefix, createURL } from "./utils"

export async function getAll() {
  return fetchJSON("/api/shares")
}

export async function get(file_id) {
  return fetchJSON(`/api/shares/${file_id}`)
}

export async function remove(hash) {
  await fetchURL(`/api/share/${hash}`, {
    method: "DELETE",
  });
}

export async function create(url, password = "", expires = "", unit = "hours") {
  url = removePrefix(url)
  url = `/api/share${url}`
  if (expires !== "") {
    url += `?expires=${expires}&unit=${unit}`
  }
  let body = "{}"
  if (password != "" || expires !== "" || unit !== "hours") {
    body = JSON.stringify({ password: password, expires: expires, unit: unit });
  }
  return fetchJSON(url, {
    method: "POST",
    body: body,
  });
}

export function getShareURL(share) {
  return createURL("share/" + share.hash, {}, false);
}
