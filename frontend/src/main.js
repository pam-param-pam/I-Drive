import { createApp } from "vue"
import router from "@/router"
import i18n from "@/i18n"
import App from "@/App.vue"
import { createPinia } from "pinia"
import Toast, { useToast } from "vue-toastification"
import "vue-toastification/dist/index.css"

import VueLazyLoad from "vue3-lazyload"
import Vue3TouchEvents from "vue3-touch-events"
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

const app = createApp(App)
console.log("validate login")
app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(Vue3TouchEvents)

app.use(VueLazyLoad, {
   // options...
})

app.use(VueVirtualScroller)

const filterBeforeCreate = (toast, toasts) => {

   for (let i = 0; i < toasts.length; i++) {
      if (toast.content === toasts[i].content) {
         toasts[i].timeout = 500
      }
   }
   return toast

}

const options = {
   transition: "Vue-Toastification__bounce",
   maxToasts: 3,
   position: "bottom-right",
   timeout: 2500,
   newestOnTop: true,
   filterBeforeCreate: filterBeforeCreate

}
app.use(Toast, options)

app.mixin({
   mounted() {
      // expose vue instance to components
      this.$el.__vue__ = this
      //expose toast instance to components to not have to call const toast = useToast() everywhere
      this.$toast = useToast()

   }
})

// provide v-focus for components
app.directive("focus", {
   mounted: async (el) => {
      // initiate focus for the element
      el.focus()
   }
})
router.isReady().then(() => app.mount("#app"))
export default app
