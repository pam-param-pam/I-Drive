import {fetchJSON, fetchURL} from "@/api/utils.js"

export async function moveToTrash(data) {
    return await fetchJSON(`/api/moveToTrash`, {
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
export async function move(data) {
    return await fetchURL(`/api/move`, {
        method: "POST",

        body: JSON.stringify(data)
    })

}
export async function remove(data) {
    return await fetchURL(`/api/delete`, {
        method: "POST",

        body: JSON.stringify(data)
    })

}
