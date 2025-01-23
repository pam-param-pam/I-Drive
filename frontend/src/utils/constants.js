export const name ="I Drive"

export const baseWS = import.meta.env.VITE_BACKEND_BASE_WS

export const baseURL = import.meta.env.VITE_BACKEND_BASE_URL

export const author = "Pam"

export const signup = true

export const version = "0.6.9 BETA"

export const logoURL = `/img/logo.jpg`

export const theme = ""

export const githubUrl = 'https://github.com/pam-param-pam/I-Drive'

export const encryptionMethods = {0: "settings.notEncrypted", 1: "settings.AES_CTR", 2: "settings.ChaCha20"}

export const encryptionMethod = {NotEncrypted: 0, AesCtr: 1, ChaCha20: 2}

export const uploadType = {
      browserInput: "browserInput",
      dragAndDropInput: "dragAndDropInput",
}

export const attachmentType = {
      thumbnail: "thumbnail",
      chunked: "chunked",
      entireFile: "entireFile",
}
export const uploadStatus = {
      preparing: "preparing",
      encrypting: "encrypting",
      finishing: "finishing",
      uploaded: "uploaded",
      uploading: "uploading",
      creating: "creating",
      failed: "failed",
      paused: "paused",
      pausing: "pausing",
      resuming: "resuming",
      canceling: "canceling",
      canceled: "canceled",
}
