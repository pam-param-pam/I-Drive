import {fetchJSON, fetchURL, removePrefix} from "./utils"


export async function breadcrumbs(folder_id) {
    if (folder_id === "/files/") {
        return []
    }
    const res = await fetchURL(`/api/breadcrumbs/${folder_id}`, {})

    return await res.json()
}
export async function getItems(folder_id) {

    return await fetchJSON("/api/folder/" + folder_id, {})
}

export async function create(data) {
    const res = await fetchURL(`/api/createfolder`, {
        method: "POST",
        body: JSON.stringify(data)
    })
    return await res.json()

}

