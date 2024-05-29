import {fetchJSON, fetchURL, getHeaders} from "./utils"

export async function getItems(folder_id) {
    let url = "/api/folder/" + folder_id
    //let headers = getHeaders(lockFrom)
    // headers: headers

    return await fetchJSON(url, {
    })

}
export async function isPasswordCorrect(folder_id, password) {
    let url = `/api/folder/password/${folder_id}`

    let response = await fetchURL(url, {
        method: "GET",
        headers: {
          "X-Folder-Password": password
        }
    })
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

    return await fetchJSON(url, {
        method: "POST",
        body: JSON.stringify(data),
        headers: headers,

    })
}
export async function create(data) {
    return await fetchJSON(`/api/folder/create`, {
        method: "POST",
        body: JSON.stringify(data)
    })

}
export async function getUsage(folderId) {

    return await fetchJSON(`/api/folder/usage/${folderId}`, {})

}

export async function changePassword(data) {

    return await fetchJSON(`/api/folder/password`, {
        method: "PATCH",

        body: JSON.stringify(data)
    })


}
