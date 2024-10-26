import {createApp} from "vue"
import router from "@/router"
import i18n from "@/i18n"
import App from "@/App.vue"
import {createPinia} from "pinia"
import Toast, {useToast} from "vue-toastification"
import "vue-toastification/dist/index.css"

import AsyncComputed from 'vue-async-computed'
import VueLazyLoad from 'vue3-lazyload'
import Vue3TouchEvents from "vue3-touch-events"


const app = createApp(App)
console.log("validate login")
app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(AsyncComputed)
app.use(Vue3TouchEvents)

app.use(VueLazyLoad, {
   // options...
})



const filterBeforeCreate = (toast, toasts) => {
   //discard it if the content is exactly the same
   if (toasts.filter(t => t.content === toast.content).length !== 0) {
      // Returning false discards the toast
      return false;
   }
   return toast;

}

const options = {
   transition: "Vue-Toastification__bounce",
   maxToasts: 3,
   position: "bottom-right",
   timeout: 2500,
   newestOnTop: true,
   filterBeforeCreate: filterBeforeCreate,

}
app.use(Toast, options)

app.mixin({
   mounted() {
      // expose vue instance to components
      this.$el.__vue__ = this
      //expose toast instance to components to not have to call const toast = useToast() everywhere
      this.$toast = useToast()

   },
})

// provide v-focus for components
app.directive("focus", {
   mounted: async (el) => {
      // initiate focus for the element
      el.focus()
   },
})
router.isReady().then(() => app.mount("#app"))
export default app
