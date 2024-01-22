import {fetchJSON, fetchURL} from "@/api/utils.js";

export async function remove(data) {
    const res = await fetchJSON(`/api/delete`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },

        body: JSON.stringify(data)
    });
    return res

}
export async function rename(data) {
    const res = await fetchURL(`/api/rename`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },

        body: JSON.stringify(data)
    });
    return res


}