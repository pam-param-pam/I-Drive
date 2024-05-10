import * as i18n from "@/i18n"
import moment from "moment"
import store from "@/store/index.js"

const mutations = {

  setFolderPassword(state, payload) {
    state.folderPasswords[payload.folderId] = payload.password;
  },
  resetFolderPassword(state, payload) {
    state.folderPasswords = {}
  },
  updateFolderPassword(state, payload) {
    if (state.folderPasswords.hasOwnProperty(payload.folderId)) {
      state.folderPasswords[payload.folderId] = payload.password;
    } else {
      // Handle if the folder password doesn't exist
    }
  },
  closeHover: (state) => {
    state.prompts.pop()
  },
  changeOpenSearchState: (state, payload) => {
    state.searchOpen = payload
  },
  toggleShell: (state) => {
    state.show = null
    state.showShell = !state.showShell;
  },
  showHover: (state, value) => {
    if (typeof value !== "object") {
      state.prompts.push({
        prompt: value,
        confirm: null,
        action: null,
        props: null,
      });
      return;
    }

    state.prompts.push({
      prompt: value.prompt, // Should not be null
      confirm: value?.confirm,
      action: value?.action,
      props: value?.props,

    });
  },
  setLoading: (state, value) => {
    state.loading = value
  },
  setReload: (state, value) => {
    state.reload = value
  },
  setToken: (state, value) => {
    state.token = value
  },
  setUser: (state, value) => {
    if (value === null) {
      state.user = null
      return;
    }

    state.user = value;
  },
  addSelected: (state, value) => {
    if (typeof value !== "object") return;
    console.log("adding to selected " + JSON.stringify(value))
    state.selected.push(value)
    console.log("selected count is: " + store.getters.selectedCount)

  },
  removeSelected: (state, value) => {
    console.log("removing from selected " + JSON.stringify(value))
    state.selected = state.selected.filter(item => item.id !== value.id);
    console.log("removed from selected " + JSON.stringify(state.selected))

  },
  resetSelected: (state) => {
    console.log("reseting selected")
    state.selected = [];
  },
  updateUser: (state, value) => {
    if (typeof value !== "object") return;

    for (let field in value) {
      if (field === "locale") {
        moment.locale(value[field]);
        i18n.default.locale = value[field];
      }

      state.user[field] = value[field];
    }
  },
  updateItems: (state, value) => {
    state.items.push(value)

  },
  setItems: (state, value) => {
    console.log("setting items")
    state.items = value
  },
  renameItem(state, { id, newName }) {
    // Find the index of the item with the given ID
    const index1 = state.items.findIndex(item => item.id === id);
    const index2 = state.selected.findIndex(item => item.id === id);

    // update item name in items
    if (index1 !== -1) {
      state.items[index1].name = newName;
    }
    // update item name in selected(important for preview)
    if (index2 !== -1) {
      state.selected[index2].name = newName;
    }
  },
  changeLockStatusAndPasswordCache(state, { folderId, newLockStatus }){
    // Find the index of the item with the given ID
    const index1 = state.items.findIndex(item => item.id === folderId);
    const index2 = state.selected.findIndex(item => item.id === folderId);

    // update item name in items
    if (index1 !== -1) {
      state.items[index1].isLocked = newLockStatus;
    }
    // update item name in selected(important for preview)
    if (index2 !== -1) {
      state.selected[index2].isLocked = newLockStatus;
    }
    this.commit('updateFolderPassword', {"folderId": folderId, "password": null});

  },
  updatePreviewInfo(state, { id, iso, focal_length, aperture, model_name, exposure_time }) {
    // Find the index of the item with the given ID
    const index1 = state.items.findIndex(item => item.id === id);
    const index2 = state.selected.findIndex(item => item.id === id);

    // update item name in items
    if (index1 !== -1) {
      state.items[index1].iso = iso;
      state.items[index1].focal_length = focal_length;
      state.items[index1].aperture = aperture;
      state.items[index1].model_name = model_name;
      state.items[index1].exposure_time = exposure_time;

    }
    // update item name in selected(important for preview)
    if (index2 !== -1) {
      state.selected[index2].iso = iso;
      state.selected[index2].focal_length = focal_length;
      state.selected[index2].aperture = aperture;
      state.selected[index2].model_name = model_name;
      state.selected[index2].exposure_time = exposure_time;
    }
  },
  updateClipboard: (state, value) => {
    state.clipboard.key = value.key;
    state.clipboard.items = value.items;
    state.clipboard.path = value.path;
  },
  resetClipboard: (state) => {
    state.clipboard.key = "";
    state.clipboard.items = [];
  },
  setUploadSpeed: (state, value) => {
    state.upload.speedMbyte = value;
  },
  setETA(state, value) {
    state.upload.eta = value;
  },
  resetUpload(state) {
    state.upload.uploads = {};
    state.upload.queue = [];
    state.upload.progress = [];
    state.upload.sizes = [];
    state.upload.id = 0;
    state.upload.speedMbyte = 0;
    state.upload.eta = 0;
  },
  setCurrentFolder(state, value) {
    state.currentFolder = value;

  },
  setPerms(state, value) {
    state.perms = value;

  },
  setSortingBy(state, value) {
    state.settings.sortingBy = value;

  },
  setSortByAsc(state, value) {
    state.settings.sortByAsc = value;

  },
  setSettings(state, value) {
    console.log("seting settings: " + value)
    let locale = value?.locale;

    if (locale === "") {
      locale = i18n.detectLocale();
    }

    moment.locale(locale);
    i18n.default.locale = locale;
    state.settings = value;

  },
  updateSettings: (state, value) => {
    if (typeof value !== "object") return;

    for (let field in value) {
      state.settings[field] = value[field];

    }

    let locale = value?.locale;
    if (locale) {

      moment.locale(locale);
      i18n.default.locale = locale;

    }

  },
  setError(state, value) {
    state.error = value
  }
};

export default mutations;
