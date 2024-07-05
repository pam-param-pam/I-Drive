import {backend_instance} from "@/api/networker.js"
import store from "@/store/index.js";

export async function getItems(folder_id, lockFrom) {
    let url = "/api/folder/" + folder_id
    let password = store.getters.getFolderPassword(lockFrom)

    let response = await backend_instance.get(url, {
        headers: {
            "x-folder-password": password
        }
    })
    return response.data
}

export async function lockWithPassword(folder_id, password, oldPassword) {
    let url = `/api/folder/password/${folder_id}`
    let headers = {}

    if (oldPassword === "") {
        oldPassword = null
    }
    else {
        headers["X-Folder-Password"] = encodeURIComponent(oldPassword)

    }
    if (password === "") {
        password = null
    }
    let data = {"new_password": password}
    let response = await backend_instance.post(url, data, {
        headers: headers
    })
    return response.data


}
export async function create(data) {
    let url = "/api/folder/create"
    let response = await backend_instance.post(url, data)
    return response.data

}
export async function getUsage(folderId, lockFrom) {
    let password = store.getters.getFolderPassword(lockFrom)

    let url = `/api/folder/usage/${folderId}`
    let response = await backend_instance.get(url, {
        headers: {
            "x-folder-password": password
        }
    })
    return response.data

}
