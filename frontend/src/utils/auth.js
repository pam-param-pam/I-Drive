import store from "@/store";
import router from "@/router";
import { Base64 } from "js-base64";
import { baseURL } from "@/utils/constants";

export function parseToken(body) {


}
export async function getUser(token) {
      const res = await fetch(`${baseURL}/auth/users/me`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Token ${token}`
        },

      });

      const body = await res.text();

      if (res.status === 200) {
        store.commit("setUser", JSON.parse(body));
        console.log(store.state.user.perm)
      } else {
        throw new Error(body);
      }

}
export async function validateLogin() {
  const token = localStorage.getItem("token");

  await getUser(token)
}

export async function login(username, password, recaptcha) {
  const data = { username, password };

  const res = await fetch(`${baseURL}/auth/token/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },

    body: JSON.stringify(data),
  });

  const body = await res.text();

  if (res.status === 200) {
    const token = JSON.parse(body).auth_token;

    localStorage.setItem("token", token);
    store.commit("token", token);
    await getUser(token)
  } else {
    throw new Error(body);
  }
}

export async function renew(jwt) {

}

export async function signup(username, password) {
  const data = { username, password };

  const res = await fetch(`${baseURL}/api/signup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (res.status !== 200) {
    throw new Error(res.status);
  }
}

export function logout() {
  document.cookie = "auth=; expires=Thu, 01 Jan 1970 00:00:01 GMT; path=/";

  store.commit("setJWT", "");
  store.commit("setUser", null);
  localStorage.setItem("jwt", null);
  router.push({ path: "/login" });
}
