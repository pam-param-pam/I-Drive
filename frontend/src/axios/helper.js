import axios from "axios"
import { logout } from "@/utils/auth.js"
import { useToast } from "vue-toastification"
import i18n from "@/i18n/index.js"

const cancelTokenMap = new Map()
const toast = useToast()


export function attachCancelSignature(config) {
   if (!config.__cancelSignature) return
   if (cancelTokenMap.has(config.__cancelSignature)) {
      cancelTokenMap.get(config.__cancelSignature).cancel(`Cancelled due to new request`)
      cancelTokenMap.delete(config.__cancelSignature)
   }
   const source = axios.CancelToken.source()
   config.cancelToken = source.token
   cancelTokenMap.set(config.__cancelSignature, source)
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
   // if (error.response && error.response.status === 403) {
   //    let errorMessage = error.response?.data?.error
   //    if (errorMessage === "errors.urlInvalidOrExpired") {
   //       router.go(0)
   //    }
   // }
}
