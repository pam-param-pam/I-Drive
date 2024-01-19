import {fetchJSON, fetchURL, removePrefix} from "./utils";


export async function breadcrumbs(folder_id) {
    if (folder_id === "/files/") {
        return []
    }
    const res = await fetchURL(`/api/breadcrumbs/${folder_id}`, {});

    return await res.json();
}
export async function getItems(url) {
    if (url === "/files/") {
        url = "/api/getroot"
    }
    else {
        url = "/api" + url.replace("/files", "")

    }

    return await fetchJSON(url, {});
}

export async function create(data) {
    const res = await fetchURL(`/api/createfolder`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },

        body: JSON.stringify(data)
    });

}

