import { useToast } from "vue-toastification"
import i18n from "@/i18n/index.js"
import throttle from "lodash.throttle"
import dayjs from "@/utils/dayjsSetup.js"

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

   if (arry.length === 1) return ".txt" //missing extension defaults to .txt
   return "." + arry[arry.length - 1]

}

const throttledToast = throttle(() => {
   const toast = useToast()
   toast.error(i18n.global.t("toasts.actionAlreadyInProgress"))
}, 1000, { trailing: false })

export function onceAtATime(fn, onBlocked) {
   let isRunning = false

   return async function(...args) {
      if (isRunning) {
         if (typeof onBlocked === "function") {
            onBlocked.call(this, ...args)
         }
         else {
            throttledToast()
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
import { useMainStore } from "@/stores/mainStore.js"

export function humanTime(date) {
   if (!date) return "-"

   const store = useMainStore()
   if (store.settings.dateFormat) {
      return dayjs(date, "YYYY-MM-DD HH:mm").format("DD/MM/YYYY, hh:mm")
   }
   return dayjs(date, "YYYY-MM-DD HH:mm").fromNow()
}