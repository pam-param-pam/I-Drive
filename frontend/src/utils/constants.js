const name = window.FileBrowser.Name || "File Browser";
//const baseURL = window.FileBrowser.BaseURL;
const baseWS = "ws://127.0.0.1:8000"
const baseURL = "http://127.0.0.1:8000"
//const baseURL = "https://demo.filebrowser.org"
const staticURL = window.FileBrowser.StaticURL;
const signup = window.FileBrowser.Signup;
const version = window.FileBrowser.Version;
const logoURL = `${staticURL}/img/logo.svg`;
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
