const name = window.FileBrowser.Name || "File Browser"
//const baseURL = window.FileBrowser.BaseURL
const baseWS = "ws://localhost:8000"
//const baseWS = "ws://192.168.1.14:8000"
//const baseWS = "wss://api.pamparampam.dev"
const baseURL = "http://localhost:8000"
//const baseURL = "http://192.168.1.14:8000"
//const baseURL = "https://api.pamparampam.dev"
const author = window.FileBrowser.author

const signup = window.FileBrowser.Signup
const version = window.FileBrowser.Version
const logoURL = `https://i.redd.it/i5s5x4bzffdb1.jpg`
const loginPage = window.FileBrowser.LoginPage
const theme = window.FileBrowser.Theme

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
}
