import {fetchJSON, fetchURL} from "./utils";

export async function getUser(token) {
  if (!token) return
  return await fetchJSON(`/auth/user/me`, {
   method: "GET",
   headers: {
     "Content-Type": "application/json",
     "Authorization": `Token ${token}`
   },
 })

}

export async function updateSettings(data) {
  const res = await fetchURL(`/api/user/updatesettings`, {
    method: "POST",

    body: JSON.stringify(data)
  });

}

export async function getTrash() {
  return await fetchJSON(`/api/trash`);

}



