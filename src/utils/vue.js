import Vue from "vue"
import VueLazyload from "vue-lazyload"
import AsyncComputed from "vue-async-computed"
import Toast from "vue-toastification"
import "vue-toastification/dist/index.css"
import Vue2TouchEvents from 'vue2-touch-events'

Vue.use(Vue2TouchEvents)
Vue.use(VueLazyload)
Vue.use(AsyncComputed)


const options = {
  transition: "Vue-Toastification__bounce",
  maxToasts: 20,
  position: "bottom-right",
  timeout: 2500,
  newestOnTop: true,

}

Vue.use(Toast, options)

Vue.config.productionTip = true



Vue.directive("focus", {
  inserted: function (el) {
    el.focus()
  },
})



export default Vue
