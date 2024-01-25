import {fetchJSON} from "@/api/utils.js";

export async function getFile(file_id) {
  return await fetchJSON(`/api/file${file_id}`, {})
}


