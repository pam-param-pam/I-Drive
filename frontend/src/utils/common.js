import { useToast } from "vue-toastification"
import i18n from "@/i18n/index.js"
import throttle from "lodash.throttle"
import dayjs from "@/utils/dayjsSetup.js"
import { useMainStore } from "@/stores/mainStore.js"

const toast = useToast()


export function isMobile() {
   return window.innerWidth <= 950
}


export function formatSeconds(seconds) {
   let h = Math.floor(seconds / 3600)
   let m = Math.floor((seconds % 3600) / 60)
   let s = Math.round(seconds % 60)
   let t = [h, m > 9 ? m : h ? "0" + m : m || "0", s > 9 ? s : "0" + s]
      .filter(Boolean)
      .join(":")
   return seconds < 0 && seconds ? `-${t}` : t
}


export function detectExtension(filename) {
   let arry = filename.split(".")

   if (arry.length === 1) return ".txt"
   return "." + arry[arry.length - 1]

}


const showThrottledToast = throttle(() => {
   showToast("error", "toasts.actionAlreadyInProgress")
}, 1000, { trailing: false })


export function onceAtATime(fn, onBlocked) {
   let isRunning = false

   return async function(...args) {
      if (isRunning) {
         if (typeof onBlocked === "function") {
            onBlocked.call(this, ...args)
         } else {
            showThrottledToast()
         }
         return
      }
      isRunning = true
      try {
         return await fn.apply(this, args)
      } finally {
         isRunning = false
      }
   }
}


export function humanTime(date) {
   if (!date) return "-"

   const store = useMainStore()
   if (store.settings.dateFormat) {
      return dayjs(date, "YYYY-MM-DD HH:mm").format("DD/MM/YYYY, hh:mm")
   }
   return dayjs(date, "YYYY-MM-DD HH:mm").fromNow()
}


export function showToast(type, content, options) {
   toast(i18n.global.t(content), { type, ...options })
}


export function capitalize(str) {
   return str.charAt(0).toUpperCase() + str.slice(1)
}

export function lazyWithLoading(importer, delay = 150) {
   let promise = null

   return () => {
      if (!promise) {
         const store = useMainStore()

         let timer = setTimeout(() => {
            store.loading = true
         }, delay)

         promise = importer()
            .finally(() => {
               clearTimeout(timer)
               store.loading = false
            })
      }

      return promise
   }
}

export function resolveItemAction(item) {
   if (item.isDir) return "dir"

   if (item.extension === ".zip") return "zip"

   if ((item.type === "Text" || item.type === "Code" || item.type === "Database") && item.size < 1024 * 1024) {
      return "editor"
   }

   return "preview"
}

