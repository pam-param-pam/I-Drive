import {fetchJSON} from "./utils";

export async function search(argumentDict) {
  let queryParams = new URLSearchParams(argumentDict);
  let url = `/api/search?${queryParams.toString()}`;


  return await fetchJSON(url)

}
