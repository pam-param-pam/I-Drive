export const name = "I Drive"

export const baseWS = import.meta.env.VITE_BACKEND_BASE_WS || "{{ VITE_BACKEND_BASE_WS }}"

export const baseURL = import.meta.env.VITE_BACKEND_BASE_URL || "{{ VITE_BACKEND_BASE_URL }}"

export const author = "Pam"

export const signup = true

export const version = "0.6.9 BETA"

export const logoURL = `/img/logo.jpg`

export const theme = ""

export const githubUrl = "https://github.com/pam-param-pam/I-Drive"

export const encryptionMethods = { 0: "settings.notEncrypted", 1: "settings.AES_CTR", 2: "settings.ChaCha20" }

export const encryptionMethod = { NotEncrypted: 0, AesCtr: 1, ChaCha20: 2 }

export const uploadType = {
   browserInput: "browserInput",
   dragAndDropInput: "dragAndDropInput"
}

export const attachmentType = {
   file: "file",
   thumbnail: "thumbnail",
   subtitle: "subtitle"
}
export const fileUploadStatus = {
   preparing: "preparing",
   uploading: "uploading",
   uploaded: "uploaded",
   waitingForSave: "waitingForSave",
   uploadFailed: "uploadFailed",
   saveFailed: "saveFailed",
   errorOccurred: "errorOccurred",
   waitingForInternet: "waitingForInternet",
   retrying: "retrying",
   fileGoneInUpload: "fileGoneInUpload",
   fileGoneInRequestProducer: "fileGoneInRequestProducer"
}

export const uploadState = {
   idle: "idle",
   uploading: "uploading",
   paused: "paused",
   noInternet: "noInternet",
   error: "error"
}

export const WebsocketEvent = {
   WEBSOCKET_ERROR: 0,
   ITEM_CREATE: 1,
   ITEM_DELETE: 2,
   ITEM_UPDATE: 3,
   ITEM_MOVE_OUT: 4,
   ITEM_MOVE_IN: 5,
   ITEM_MOVE_TO_TRASH: 6,
   ITEM_RESTORE_FROM_TRASH: 7,
   MESSAGE_UPDATE: 8,
   MESSAGE_SENT: 9,
   FOLDER_LOCK_STATUS_CHANGE: 10,
   FORCE_LOGOUT: 11,
   NEW_DEVICE_LOG_IN: 12,
   DEVICE_CONTROL_REQUEST: 13,
   DEVICE_CONTROL_REPLY: 14,
   DEVICE_CONTROL_COMMAND: 15,
   DEVICE_CONTROL_STATUS: 16,
   NEW_NOTIFICATION: 17
}