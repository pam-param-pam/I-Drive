import Vue from "vue"
import VueLazyload from "vue-lazyload"
import AsyncComputed from "vue-async-computed"
import Toast from "vue-toastification"
import "vue-toastification/dist/index.css"
import Vue2TouchEvents from 'vue2-touch-events'

Vue.use(Vue2TouchEvents)
Vue.use(VueLazyload)
Vue.use(AsyncComputed)




Vue.use(Toast, options)

Vue.config.productionTip = true



Vue.directive("focus", {
  inserted: function (el) {
    el.focus()
  },
})



export default Vue
