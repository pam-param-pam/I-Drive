import store from "@/store";
import router from "@/router";
import {baseURL} from "@/utils/constants";
import {getUser} from "@/api/user.js";



export async function validateLogin() {
  const token = localStorage.getItem("token");

  const body = await getUser(token)
  store.commit("setUser", body.user);
  store.commit("setSettings", body.settings);
  store.commit("setPerms", body.perms);
  store.commit("setToken", token);
}

export async function login(username, password, recaptcha) {
  const data = {username, password};

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
    store.commit("setToken", token);
    await getUser(token)
  } else {
    throw new Error(body);
  }
}


export async function signup(username, password) {
  const data = {username, password};

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

  store.commit("setUser", null);
  store.commit("setSettings", null);
  store.commit("setToken", null);
  localStorage.removeItem("token");

  router.push({path: "/login"});
}
