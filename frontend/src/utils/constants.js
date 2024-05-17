const name = window.FileBrowser.Name || "File Browser";
//const baseURL = window.FileBrowser.BaseURL;
const baseWS = "ws://localhost:8000"
//const baseWS = "ws://192.168.1.14:8000"
//const baseWS = "wss://api.pamparampam.dev"
//const baseWS = "aaa"

const baseURL = "http://localhost:8000"
//const baseURL = "http://192.168.1.14:8000"
//const baseURL = "https://api.pamparampam.dev"

const staticURL = window.FileBrowser.StaticURL;
const signup = window.FileBrowser.Signup;
const version = window.FileBrowser.Version;
const logoURL = `https://i.redd.it/i5s5x4bzffdb1.jpg`;
const loginPage = window.FileBrowser.LoginPage;
const theme = window.FileBrowser.Theme;
const enableThumbs = window.FileBrowser.EnableThumbs;
const resizePreview = window.FileBrowser.ResizePreview;
const enableExec = window.FileBrowser.EnableExec;
const tusSettings = window.FileBrowser.TusSettings;
const origin = window.location.origin;
const tusEndpoint = `/api/tus`;

export {
  name,
  baseURL,
  staticURL,
  logoURL,
  signup,
  version,
  loginPage,
  theme,
  enableThumbs,
  resizePreview,
  enableExec,
  tusSettings,
  origin,
  tusEndpoint,
  baseWS,
};
