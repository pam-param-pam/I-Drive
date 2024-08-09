import Vue from "vue"
import VueLazyload from "vue-lazyload"
import AsyncComputed from "vue-async-computed"
import Toast from "vue-toastification"
import "vue-toastification/dist/index.css"
import VueNativeSock from 'vue-native-websocket'
import Vue2TouchEvents from 'vue2-touch-events'
import {baseWS} from "@/utils/constants.js"
import Dropdown from 'vue-simple-search-dropdown'

Vue.use(Vue2TouchEvents)
Vue.use(VueLazyload)
Vue.use(AsyncComputed)

Vue.use(Dropdown)

const options = {
  transition: "Vue-Toastification__bounce",
  maxToasts: 20,
  position: "bottom-right",
  timeout: 2500,
  newestOnTop: true,
  /*
  filterToasts: toasts => {
    // Keep track of existing types
    const types = {}
    const texts = {}
    return toasts.reduce((aggToasts, toast) => {
      // Check if type was not seen before
      if (!types[toast.type] && !texts[toast.text]) {
        aggToasts.push(toast)
        texts[toast.text] = true
        types[toast.type] = true

      }
      return aggToasts
    }, [])
  }
  
   */
}

Vue.use(Toast, options)

Vue.config.productionTip = true



Vue.directive("focus", {
  inserted: function (el) {
    el.focus()
  },
})



export default Vue
