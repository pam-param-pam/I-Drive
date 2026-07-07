export const name = "I Drive"

export const baseWS = import.meta.env.VITE_BACKEND_BASE_WS || "{{ VITE_BACKEND_BASE_WS }}"

export const baseURL = import.meta.env.VITE_BACKEND_BASE_URL || "{{ VITE_BACKEND_BASE_URL }}"

export const author = "Pam"

export const signup = true

export const version = "1.0.0 ALPHA"

export const logoURL = `/img/logo.jpg`

export const theme = ""

export const githubUrl = "https://github.com/pam-param-pam/I-Drive"

export const encryptionMethods = { 0: "settings.notEncrypted", 1: "settings.AES_CTR", 2: "settings.ChaCha20" }

export const encryptionMethod = { NotEncrypted: 0, AesCtr: 1, ChaCha20: 2 }

export const filesInTrash = 7

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
   NOTIFICATIONS_UPDATE: 13
}

export const PreviewEvent = {
   OPEN: "file_open",
   MEDIA_LOADED: "media_loaded",
   MEDIA_TIME_UPDATE: "time_update",
   MEDIA_SEEK: "seek",
   MEDIA_VOLUME_CHANGE: "volume_change",
   MEDIA_PLAY: "play",
   MEDIA_PAUSE: "pause",
   FULLSCREEN_CHANGE: "fullscreen_change",
   SUBTITLE_CHANGE: "subtitle_change",
   EDITOR_CLEAN_CHANGE: "editor_clean_change",
   DOWNLOAD: "download"
}

export const NotificationKind = {
   GENERAL: "general",
   NEW_DEVICE_LOGIN: "new_device_login",
   FOLDER_LOCK_CHANGE: "folder_lock_change"
}

export const ClientsideDecryptionMethods = {
   0: "settings.always",
   1: "settings.desktopOnly",
   2: "settings.downloadsOnly",
   3: "settings.noDecryption"
}

export const ClientsideDecryptionMethod = {
   ALWAYS: 0,
   DESKTOP_ONLY: 1,
   DOWNLOADS_ONLY: 2,
   NO_DECRYPTION: 3
}