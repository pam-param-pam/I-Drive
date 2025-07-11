import { createApp } from "vue"
import router from "@/router"
import i18n from "@/i18n"
import App from "@/App.vue"
import { createPinia } from "pinia"
import Toast, { useToast } from "vue-toastification"
import "vue-toastification/dist/index.css"

import VueLazyLoad from "vue3-lazyload"
import Vue3TouchEvents from "vue3-touch-events"
import VueVirtualScroller from "vue-virtual-scroller"
import "vue-virtual-scroller/dist/vue-virtual-scroller.css"

const app = createApp(App)

app.use(router)
app.use(i18n)
app.use(Vue3TouchEvents)

app.use(VueLazyLoad, {
   error: '/img/failed.svg',
   throttleWait: 10000
})

app.use(VueVirtualScroller)
app.use(createPinia())


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
      setTimeout(() => {
         el.focus()
         //for inputs
         let pos = el.value.lastIndexOf(".")
         el.setSelectionRange(pos, pos)
      }, 50)
   }
})
router.isReady().then(() => app.mount("#app"))

// // Save original console methods //todo
// const originalLog = console.log
// const originalWarn = console.warn
// const originalError = console.error
//
//
// // Custom logger function
// function customLogger(type, message) {
//    const mainStore = useMainStore()
//    mainStore.pushShellContent({ type: type, text: message })
// }
//
//
// // Override console.log
// console.log = function(...args) {
//    customLogger("log", ...args)
//    originalLog.apply(console, args)
// }
//
// // Override console.warn
// console.warn = function(...args) {
//    customLogger("warn", ...args)
//    originalWarn.apply(console, args)
// }
//
// // Override console.warn
// console.error = function(...args) {
//    customLogger("error", ...args)
//    originalError.apply(console, args)
// }

export default app

