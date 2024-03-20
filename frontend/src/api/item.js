import {fetchJSON, fetchURL} from "@/api/utils.js"

export async function remove(data) {
    return await fetchJSON(`/api/delete`, {
        method: "POST",
        body: JSON.stringify(data)
    })

}
export async function rename(data) {
    return await fetchURL(`/api/rename`, {
        method: "POST",

        body: JSON.stringify(data)
    })


}