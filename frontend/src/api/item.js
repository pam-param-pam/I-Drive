import {fetchJSON, fetchURL} from "@/api/utils.js"

export async function moveToTrash(data) {
    return await fetchJSON(`/api/item/moveToTrash`, {
        method: "POST",
        body: JSON.stringify(data)
    })
}

export async function rename(data) {
    return await fetchURL(`/api/item/rename`, {
        method: "POST",

        body: JSON.stringify(data)
    })

}
export async function move(data) {
    return await fetchURL(`/api/item/move`, {
        method: "POST",

        body: JSON.stringify(data)
    })

}
export async function remove(data) {
    return await fetchJSON(`/api/item/delete`, {
        method: "POST",

        body: JSON.stringify(data)
    })


}
