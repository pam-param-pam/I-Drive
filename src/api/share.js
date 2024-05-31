import { fetchURL, fetchJSON} from "./utils"
import {backend_instance} from "@/api/networker.js";

export async function getAllShares() {
  let url = "/api/shares"
  let response = await backend_instance.get(url);
  return response.data;
}

export async function getShare(token, folderId= "") {
  let url = `/api/share/${token}`
  let response = await backend_instance.get(url, {
    headers: {
      "Authorization": false,
    }
  });
  return response.data;
}

export async function removeShare(data) {
  let url = "/api/share/delete"
  let response = await backend_instance.patch(url, data);
  return response.data;

}

export async function createShare(data) {
  let url = "/api/share/create"
  let response = await backend_instance.post(url, data);
  return response.data;

}


