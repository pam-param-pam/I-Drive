import axios from "axios"
import { logout } from "@/utils/auth.js"
import { useToast } from "vue-toastification"
import i18n from "@/i18n/index.js"
import router from "@/router/index.js"

const toast = useToast()
const cancelTokenMap = new Map()

function normalizeCancelSignatures(value) {
   if (!value) return []
   if (Array.isArray(value)) return [...new Set(value)]
   return [value]
}

function deleteSourceFromAllSignatures(source) {
   for (const [signature, mappedSource] of cancelTokenMap.entries()) {
      if (mappedSource === source) {
         cancelTokenMap.delete(signature)
      }
   }
}

export function attachCancelSignature(config) {
   const signatures = normalizeCancelSignatures(config.__cancelSignature)

   if (signatures.length === 0) return

   const sourcesToCancel = new Set()

   for (const signature of signatures) {
      const previousSource = cancelTokenMap.get(signature)

      if (previousSource) {
         sourcesToCancel.add(previousSource)
      }
   }

   for (const source of sourcesToCancel) {
      source.cancel("Cancelled due to new request")
      deleteSourceFromAllSignatures(source)
   }

   const source = axios.CancelToken.source()

   config.cancelToken = source.token

   for (const signature of signatures) {
      cancelTokenMap.set(signature, source)
   }
}


export function cancelRequestBySignature(signature) {
   if (cancelTokenMap.has(signature)) {
      cancelTokenMap.get(signature).cancel(`Cancelled due to new request`)
      cancelTokenMap.delete(signature)
   }
}


export async function parseBinaryJsonResponse(response, config) {
   if (!response) return;

   const contentType = response.headers["content-type"] || "";
   const isJson = contentType.includes("application/json");

   if (!isJson) return;

   // --- handle binary ---
   if (config.responseType === "arraybuffer" && response.data instanceof ArrayBuffer) {
      const decoder = new TextDecoder("utf-8");
      try {
         response.data = JSON.parse(decoder.decode(response.data));
      } catch (e) {
         console.warn("Failed to parse ArrayBuffer JSON:", e);
      }
      return;
   }

   if (config.responseType === "blob" && response.data instanceof Blob) {
      try {
         response.data = JSON.parse(await response.data.text());
      } catch (e) {
         console.warn("Failed to parse Blob JSON:", e);
      }
      return;
   }

   if (config.responseType === "text" && typeof response.data === "string") {
      try {
         let parsed = JSON.parse(response.data);

         // handle double-encoded JSON
         if (typeof parsed === "string") {
            parsed = JSON.parse(parsed);
         }

         response.data = parsed;
      } catch (e) {
         // silently ignore — it wasn't JSON
      }
   }
}


export function noWifi(error) {
   return (!error.response && error.code === "ERR_NETWORK") || error.response && error.response.status === 502
}


export function shouldRetry469(error) {
   return error.response?.status === 469 && error.config.__manage469 !== false
}


export async function displayErrorToastIfNeeded(error) {
   let errorMessage = error.response?.data?.error
   let errorDetails = error.response?.data?.details
   if (!errorMessage && errorMessage !== "") errorMessage = "Unexpected error"
   if (!errorDetails && errorDetails !== "") errorDetails = "Report this"
   if (error.response?.status === 401) {
      await logout()

      errorMessage = i18n.global.t("toasts.unauthorized")
      errorDetails = i18n.global.t("toasts.sessionExpired")
   }
   if (error.code === "ERR_NETWORK") {
      errorMessage = i18n.global.t("errors.noConnection")
      errorDetails = i18n.global.t("errors.noConnectionDetails")
   }
   if (error.config.__displayErrorToast !== false) {
      toast.error(`${i18n.global.t(errorMessage)}\n${i18n.global.t(errorDetails)}`, {
         timeout: 5000,
         position: "bottom-right"
      })
   }
}


export async function handleResourceURLExpiredIfNeeded(error) {
   if (error.response?.status !== 403) {
      return
   }

   const errorMessage = error.response?.data?.error

   if (errorMessage === "errors.urlInvalidOrExpired") {
      const key = "lastResourceUrlReload"
      const now = Date.now()
      const lastReload = Number(localStorage.getItem(key) || 0)

      if (now - lastReload >= 10_000) {
         localStorage.setItem(key, now.toString())
         router.go(0)
      }
   }
}
