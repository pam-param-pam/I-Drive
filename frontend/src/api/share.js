import { fetchURL, fetchJSON, removePrefix, createURL } from "./utils"
import {baseURL} from "@/utils/constants.js";

export async function getAll() {
  return fetchJSON("/api/shares")
}

export async function get(file_id) {
  return fetchJSON(`/api/shares/${file_id}`)
}

export async function remove(data) {
  await fetchURL(`/api/deleteshare`, {
    method: "POST",
    body: JSON.stringify(data)

  });
}

export async function create(data) {




  return fetchJSON("/api/createshare", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function getShareURL(share) {
  return baseURL + "/share/" + share.token

}
export function getDownloadLink(share) {
  return "http://127.0.0.1:9000/stream/" + share.token

}
