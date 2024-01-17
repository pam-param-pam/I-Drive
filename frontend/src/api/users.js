import { fetchURL, fetchJSON } from "./utils";

export async function get() {
  return fetchJSON(`/api/users/me`, {});
}
