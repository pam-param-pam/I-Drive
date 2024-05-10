import {fetchJSON} from "./utils";

export async function search(query) {
  return await fetchJSON(`/api/search?query=${query}`)

}
