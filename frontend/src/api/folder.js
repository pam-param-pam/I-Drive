import {fetchJSON, fetchURL} from "./utils"


export async function breadcrumbs(folder_id) {
    return await fetchJSON(`/api/folder/breadcrumbs/${folder_id}`, {})

}
export async function getItems(folder_id, includeTrash) {
    return await fetchJSON("/api/folder/" + folder_id + "/?includeTrash=False", {})
}

export async function create(data) {
    return await fetchJSON(`/api/folder/create`, {
        method: "POST",
        body: JSON.stringify(data)
    })

}
export async function getUsage(folderId) {

    return await fetchJSON(`/api/folder/usage/${folderId}/`, {});

}

