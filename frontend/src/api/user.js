import {fetchJSON, fetchURL} from "./utils";

export async function getUser(token) {
  if (!token) return
  return await fetchJSON(`/auth/users/me`, {
   method: "GET",
   headers: {
     "Content-Type": "application/json",
     "Authorization": `Token ${token}`
   },
 })

}

export async function updateSettings(data) {
  const res = await fetchURL(`/api/updatesettings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },

    body: JSON.stringify(data)
  });

}
