const name = window.FileBrowser.Name

const baseWS = import.meta.env.VITE_BACKEND_BASE_WS
const baseURL = import.meta.env.VITE_BACKEND_BASE_URL
const author = window.FileBrowser.author

const signup = window.FileBrowser.Signup
const version = window.FileBrowser.Version
const logoURL = `/img/logo.jpg`
const loginPage = window.FileBrowser.LoginPage
const theme = window.FileBrowser.Theme

const chunkSize = 25 * 1023 * 1024 // <25MB in bytes

export {
   name,
   baseURL,
   logoURL,
   signup,
   version,
   author,
   loginPage,
   theme,
   baseWS,
   chunkSize
}
