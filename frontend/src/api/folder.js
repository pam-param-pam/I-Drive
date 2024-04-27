import {fetchJSON, fetchURL} from "./utils"
import store from "@/store/index.js";


export async function breadcrumbs(folder_id) {
    return await fetchJSON(`/api/folder/breadcrumbs/${folder_id}`, {})

}
export async function getItems(folder_id, includeTrash) {
    // TODO password logic here
    let password = store.getters.getFolderPassword(folder_id)
    let url = "/api/folder/" + folder_id + "/"
    if (includeTrash) url = url + "?includeTrash=True"
    //if (password?.length !== undefined) url = url + `?password=${password}`

    if (password?.length !== undefined) {
        console.log("password is not null")
        return await fetchJSON(url, {
            headers: {
                "X-Folder-Password": password
            }
          }
        )
    }
    return await fetchJSON(url, {})

}
export async function isPasswordCorrect(folder_id, password) {
    let url = `/api/folder/password/${folder_id}`

    let response = await fetchURL(url, {
        method: "GET",
        headers: {
          "X-Folder-Password": password
        }
    })
    return response.status === 200;



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

export async function changePassword(data) {

    return await fetchJSON(`/api/folder/password`, {
        method: "PATCH",

        body: JSON.stringify(data)
    })


}
