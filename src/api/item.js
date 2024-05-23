import {fetchJSON, fetchURL} from "@/api/utils.js"

export async function moveToTrash(data) {
    return await fetchURL(`/api/item/moveToTrash`, {
        method: "PATCH",
        body: JSON.stringify(data)
    })
}

export async function restoreFromTrash(data) {
    return await fetchURL(`/api/item/restore`, {
        method: "PATCH",
        body: JSON.stringify(data)
    })
}

export async function rename(data) {
    return await fetchURL(`/api/item/rename`, {
        method: "PATCH",

        body: JSON.stringify(data)
    })

}
export async function move(data) {
    return await fetchURL(`/api/item/move`, {
        method: "PATCH",

        body: JSON.stringify(data)
    })

}
export async function remove(data) {
    return await fetchJSON(`/api/item/delete`, {
        method: "DELETE",

        body: JSON.stringify(data)
    })


}
