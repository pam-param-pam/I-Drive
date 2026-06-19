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


export function showToast(type, content, options = {}, args = {}) {
   toast(i18n.global.t(content, args), { type, ...options })
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
            store.itemsLoading = true
         }, delay)

         promise = importer()
            .finally(() => {
               clearTimeout(timer)
               store.itemsLoading = false
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
   if (isAxiosError(err)) {
      if (err.response) {
         return {
            code: err.response.status,
            error: err.response.data?.error,
            details: err.response.data?.details || "errors.requestFailed",
            raw: err
         }
      }

      if (err.request) {
         if (!navigator.onLine) {
            return {
               code: 0,
               error: null,
               details: "errors.noInternet",
               raw: err
            }
         }

         if (err.code === "ECONNABORTED") {
            return {
               code: 0,
               error: null,
               details: "errors.timeout",
               raw: err
            }
         }

         return {
            code: 0,
            error: null,
            details: "errors.noResponse",
            raw: err
         }
      }
   }

   if (err instanceof DOMException) {
      return {
         code: 999,
         error: "errors.domError",
         details: err.message,
         raw: err,
      }
   }

   if (err instanceof Error) {
      return {
         code: 999,
         error: "errors.clientError",
         details: err.message,
         raw: err,
      }
   }

   if (isPlainObject(err)) {
      return {
         code: err.code ?? 999,
         error: err.error ?? null,
         details: err.details,
         raw: err,
      }
   }

   return {
      code: 999,
      error: "errors.clientError",
      details: typeof err === "string" ? err : String(err),
      raw: err,
   }
}

export function resolveItemAction(item) {
   if (item.isDir) return "dir"
   if (item.extension === ".zip") return "zip"
   return "preview"
}


export function encodePath(path) {
   return btoa(
      encodeURIComponent(path).replace(/%([0-9A-F]{2})/g, (_, p1) =>
         String.fromCharCode("0x" + p1)
      )
   )
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "")
}

export function decodePath(value) {
   const padding = "=".repeat((4 - (value.length % 4)) % 4)
   const base64 = value.replace(/-/g, "+").replace(/_/g, "/") + padding

   return decodeURIComponent(
      atob(base64)
         .split("")
         .map(c => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
         .join("")
   )
}

export function formatDuration(seconds) {
   if (seconds == null || !Number.isFinite(seconds)) {
      return null
   }

   const total = Math.floor(seconds)
   const s = total % 60
   const m = Math.floor((total / 60) % 60)
   const h = Math.floor(total / 3600)

   const pad = n => String(n).padStart(2, '0')

   return h > 0
      ? `${pad(h)}:${pad(m)}:${pad(s)}`
      : `${pad(m)}:${pad(s)}`
}
