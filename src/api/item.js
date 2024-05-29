import {fetchJSON, fetchURL, getHeaders} from "@/api/utils.js"
import store from "@/store/index.js";

export async function moveToTrash(data) {

    return await fetchURL(`/api/item/moveToTrash`, {
        method: "PATCH",
        body: JSON.stringify(data)
    })
}
export async function breadcrumbs(folder_id) {
    // const headers = getHeaders(resource.lockfrom)
        //        headers: headers
    return await fetchJSON(`/api/folder/breadcrumbs/${folder_id}`, {
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
