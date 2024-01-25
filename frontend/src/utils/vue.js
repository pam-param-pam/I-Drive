import Vue from "vue";
import VueLazyload from "vue-lazyload";
import AsyncComputed from "vue-async-computed";
import Toast from "vue-toastification";
import "vue-toastification/dist/index.css";
import VueNativeSock from 'vue-native-websocket'

Vue.use(VueLazyload);
Vue.use(AsyncComputed);
const token = localStorage.getItem("token");
// todo do this after login cuz token is null
// todo and so is the the websocket connection one the first login
Vue.use(VueNativeSock, 'ws://localhost:8000/user', {reconnectionDelay: 5000, reconnection: true, protocol: token})

const options = {
  transition: "Vue-Toastification__bounce",
  maxToasts: 20,
  position: "bottom-right",
  timeout: 2500,

  newestOnTop: true
};

Vue.use(Toast, options);

Vue.config.productionTip = true;



Vue.directive("focus", {
  inserted: function (el) {
    el.focus();
  },
});



export default Vue;
