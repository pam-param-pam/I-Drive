import {fetchURL, fetchJSON} from "./utils";
import {baseURL} from "@/utils/constants.js";
import store from "@/store/index.js";

export async function getUser(token) {
  if (!token) return
  const res = await fetch(`${baseURL}/auth/users/me`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Token ${token}`
    },
  });

  const body = await res.json();
  if (res.status === 200) {
    return body

  } else {
    throw new Error(body);
  }

}

export async function updateSettings(data) {
  console.log(data)
  const res = await fetchURL(`/api/updatesettings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },

    body: JSON.stringify(data)
  });

}
