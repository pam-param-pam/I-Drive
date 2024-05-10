import store from "@/store";
import router from "@/router";
import {baseURL, baseWS} from "@/utils/constants";
import {getUser} from "@/api/user.js";
import Vue from "vue";
import VueNativeSock from "vue-native-websocket";



export async function validateLogin() { //this isn't really validate login - more like finish login xD
  const token = localStorage.getItem("token");

  const body = await getUser(token)
  store.commit("setUser", body.user);
  store.commit("setSettings", body.settings);
  store.commit("setPerms", body.perms);
  store.commit("setToken", token);
  Vue.use(VueNativeSock, baseWS + "/user", {reconnectionDelay: 5000, reconnection: true, protocol: token})

}

export async function login(username, password) {
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
    await validateLogin()
  } else {
    const error = new Error();
    error.status = res.status;
    throw error
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

export async function logout() {
  let token = store.state.token
  if (token) {
    const res = await fetch(`${baseURL}/auth/token/logout`, {
      method: "POST",
      headers: {
        "Authorization": `Token ${token}`,
      },

    });
  }


  store.commit("setUser", null);
  store.commit("setSettings", null);
  store.commit("setToken", null);
  store.commit("setCurrentFolder", null);
  store.commit("setItems", null);
  store.commit("setPerms", null);
  store.commit("resetFolderPassword", null);

  localStorage.removeItem("token");

  router.push({path: "/login"});
}
