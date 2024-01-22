import Vue from "vue";
import Noty from "noty";
import VueLazyload from "vue-lazyload";
import AsyncComputed from "vue-async-computed";
import Toast from "vue-toastification";
import "vue-toastification/dist/index.css";
import VueNativeSock from 'vue-native-websocket'
import { baseWS } from "@/utils/constants";

Vue.use(VueLazyload);
Vue.use(AsyncComputed);
const token = localStorage.getItem("token");

Vue.use(VueNativeSock, 'ws://localhost:8000/user', {reconnectionDelay: 5000, reconnection: true, protocol: token})

const options = {
  transition: "Vue-Toastification__bounce",
  maxToasts: 20,
  newestOnTop: true
};

Vue.use(Toast, options);

Vue.config.productionTip = true;

const notyDefault = {
  type: "info",
  layout: "bottomRight",
  timeout: 1000,
  progressBar: true,
};


Vue.prototype.$showError = (error, displayReport = true) => {
  this.$toast.error(error || error.message, {
    timeout: 2000,
    position: "bottom-right",

  });

};

Vue.directive("focus", {
  inserted: function (el) {
    el.focus();
  },
});






export default Vue;
