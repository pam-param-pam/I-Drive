import store from "@/store/index.js";

const actions = {
  promptCallback: (newName) => {
      store.getters.currentPrompt.callback(newName)
  }
}
export default actions;
