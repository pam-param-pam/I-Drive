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

function isAxiosError(err) {
   return (
      err &&
      typeof err === "object" &&
      err.isAxiosError === true
   )
}

function isPlainObject(obj) {
   return (
      obj &&
      typeof obj === "object" &&
      obj.constructor === Object
   )
}
export function normalizeError(err) {
   // 1. Axios error (most structured → handle first)
   if (isAxiosError(err)) {
      // 1. Server responded (HTTP error)
      if (err.response) {
         return {
            code: err.response.status,
            details: err.response.data?.details || "Request failed",
            raw: err
         }
      }

      // 2. Request sent but no response
      if (err.request) {
         // browser-specific network errors
         if (!navigator.onLine) {
            return {
               code: 0,
               details: "No internet connection",
               raw: err
            }
         }

         if (err.code === "ECONNABORTED") {
            return {
               code: 0,
               details: "Request timeout",
               raw: err
            }
         }

         return {
            code: 0,
            details: "Server did not respond",
            raw: err
         }
      }
   }

   // 2. DOMException (e.g. DataCloneError, AbortError)
   if (err instanceof DOMException) {
      return {
         code: 999,
         details: err.message || "DOM operation failed",
         raw: err
      }
   }

   // 3. Standard JS Error
   if (err instanceof Error) {
      return {
         code: 999,
         details: err.message || "Unknown error",
         raw: err
      }
   }

   // 4. User-supplied object (message + code)
   if (isPlainObject(err)) {
      return {
         code: err.code ?? 999,
         details: err.details ?? String(err),
         raw: err
      }
   }
   // 5. String / unknown
   return {
      code: 999,
      details: typeof err === "string" ? err : String(err),
      raw: err
   }
}

export function resolveItemAction(item) {
   if (item.isDir) return "dir"
   if (item.extension === ".zip") return "zip"
   return "preview"
}

