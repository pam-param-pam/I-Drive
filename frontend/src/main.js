import {createApp} from "vue"
import router from "@/router"
import i18n from "@/i18n"
import App from "@/App.vue"
import {createPinia} from "pinia"
import Toast, {useToast} from "vue-toastification"
import "vue-toastification/dist/index.css"

import AsyncComputed from 'vue-async-computed'
import VueLazyLoad from 'vue3-lazyload'


const app = createApp(App)
console.log("validate login")

app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(AsyncComputed)
app.use(VueLazyLoad, {
   // options...
})
const options = {
   transition: "Vue-Toastification__bounce",
   maxToasts: 20,
   position: "bottom-right",
   timeout: 2500,
   newestOnTop: true,

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
