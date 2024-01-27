import store from "@/store";
import { baseURL } from "@/utils/constants";
import { encodePath } from "@/utils/url";
import vue from "@/utils/vue.js";
import {logout} from "@/utils/auth.js";

export async function fetchURL(url, opts, auth = true) {
  opts = opts || {};
  opts.headers = opts.headers || {};

  let { headers, ...rest } = opts;
  let res;
  try {
    res = await fetch(`${baseURL}${url}`, {
      headers: {
        "Authorization": `Token ${store.state.token}`,
        ...headers,
      },
      ...rest,
    });
  } catch (e){
    console.log("Error happened:" + e)
    vue.$toast.error("Unexpected, report this", {
      timeout: 0,
      position: "bottom-right",
    });
    const error = new Error(e);
    error.status = 0;
    throw error;
  }

  if (res.status < 200 || res.status > 299) {
    let res_text = await res.text()

    const error = new Error(res_text);
    error.status = res.status;
    if (auth && res.status === 401) {
      logout();
    }
    let message = "Unexpected report this"
    if (res_text.length < 150) {
      message = res_text
    }

    vue.$toast.error(`${(res.status)}: ${message}`, {
      timeout: 5000,
      position: "bottom-right",
    });

    throw error
  }
  return res;
}

export async function fetchJSON(url, opts) {
  const res = await fetchURL(url, opts);

  return res.json();

}

export function removePrefix(url) {
  url = url.split("/").splice(2).join("/");

  if (url === "") url = "/";
  if (url[0] !== "/") url = "/" + url;
  return url;
}

export function createURL(endpoint, params = {}, auth = true) {
  let prefix = baseURL;
  if (!prefix.endsWith("/")) {
    prefix = prefix + "/";
  }
  const url = new URL(prefix + encodePath(endpoint), origin);

  const searchParams = {
    ...(auth && { auth: store.state.jwt }),
    ...params,
  };

  for (const key in searchParams) {
    url.searchParams.set(key, searchParams[key]);
  }

  return url.toString();
}
export function sortItems(items) {
  // Create a shallow copy of the items array
  const itemsCopy = items.slice();

  const sortingKey = store.state.settings.sortingBy
  const isAscending = store.state.settings.sortByAsc

  return itemsCopy.sort((a, b) => {
    let aValue = a[sortingKey];
    let bValue = b[sortingKey];

    if (isAscending) {
      return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
    } else {
      return bValue < aValue ? -1 : bValue > aValue ? 1 : 0;
    }
  });
}