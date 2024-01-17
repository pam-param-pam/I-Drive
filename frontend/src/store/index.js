import Vue from "vue";
import Vuex from "vuex";
import mutations from "./mutations";
import getters from "./getters";
import upload from "./modules/upload";

Vue.use(Vuex);

const state = {
  user: null,
  clipboard: {
    key: "",
    items: [],
  },
  items: null,
  perms: null,
  settings: null,
  currentFolder: null,
  progress: 0,
  loading: false,
  reload: false,
  selected: [],
  prompts: [],
  showShell: false,
};

export default new Vuex.Store({
  strict: true,
  state,
  getters,
  mutations,
  modules: { upload },
});
