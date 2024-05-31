import {fetchJSON, fetchURL, getHeaders} from "./utils"
import {backend_instance} from "@/api/networker.js";

export async function getItems(folder_id) {
    let url = "/api/folder/" + folder_id
    let response = await backend_instance.get(url);
    return response.data;
}
export async function isPasswordCorrect(folder_id, password) {
    let url = `/api/folder/password/${folder_id}`
    let response = await backend_instance.get(url, {
        headers: {
            "Content-Type": "application/json",
            "X-Folder-Password": password
        }
    });
    return response.status === 204
}

export async function lockWithPassword(folder_id, password, oldPassword) {
    let url = `/api/folder/password/${folder_id}`
    const headers = {}

    if (oldPassword === "") {
        oldPassword = null
    }
    else {
        headers["X-Folder-Password"] = encodeURIComponent(oldPassword);

    }
    if (password === "") {
        password = null
    }
    let data = {"new_password": password}
    let response = await backend_instance.post(url, data, {
        headers: headers
    });
    return response.data;


}
export async function create(data) {
    let url = "/api/folder/create"
    let response = await backend_instance.post(url, data);
    return response.data;

}
export async function getUsage(folderId) {
    let url = `/api/folder/usage/${folderId}`
    let response = await backend_instance.get(url);
    return response.data;

}
