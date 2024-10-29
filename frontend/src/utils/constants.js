export const name ="I drive"
export const baseWS = import.meta.env.VITE_BACKEND_BASE_WS
export const baseURL = import.meta.env.VITE_BACKEND_BASE_URL
export const author = "Pam"
export const signup = true
export const version = "0.6.9 BETA"
export const logoURL = `/img/logo.jpg`
export const theme = ""
export const chunkSize = 25 * 1023 * 1024 // <25MB in bytes

export const githubUrl = 'https://github.com/pam-param-pam/I-Drive'
export const encryptionMethods = {1: "AES CTR", 2: "ChaCha20"}

export const discordFileName = "Kocham Alternatywki"
export const uploadType = {
      browserInput: "browserInput",
      dragAndDropInput: "dragAndDropInput",
}

export const requestType = {
      multiAttachment: "multiAttachment",
      chunked: "chunked",
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

}