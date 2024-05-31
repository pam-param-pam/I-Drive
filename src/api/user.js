import {fetchJSON, fetchURL} from "./utils"
import {backend_instance} from "@/api/networker.js";

export async function getUser(token) {
  if (!token) return
  return await fetchJSON(`/auth/user/me`, {
   method: "GET",
   headers: {
     "Content-Type": "application/json",
     "Authorization": `Token ${token}`
   },
 }, false)

}

export async function changePassword(data) {
  let url = `/api/user/changepassword`
  await backend_instance.post(url, data);

}

export async function updateSettings(data) {
  let url = `/api/user/updatesettings`
  await backend_instance.post(url, data);

}

export async function getTrash() {
  let url = `/api/trash`
  let response = await backend_instance.get(url);
  return response.data;
}



