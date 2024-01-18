import { createURL, fetchURL, removePrefix } from "./utils";
import { baseURL } from "@/utils/constants";
import store from "@/store";
import { upload as postTus, useTus } from "./tus";


export async function breadcrumbs(folder_id) {
    if (folder_id === "/files/") {
        return []
    }
    const res = await fetchURL(`/api/breadcrumbs/${folder_id}`, {});

    return await res.json();
}