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
   } else {
      console.warn("Couldn't find request to cancel with signature: " + signature)
   }
}


export async function parseBinaryJsonResponse(response, config) {
   if (!response) return

   const contentType = response.headers["content-type"] || ""
   const isBinary = config.responseType === "arraybuffer" || config.responseType === "blob"
   const isJson = contentType.includes("application/json")

   if (!isBinary || !isJson) return

   let errorText = ""

   if (response.data instanceof ArrayBuffer) {
      const decoder = new TextDecoder("utf-8")
      errorText = decoder.decode(response.data)
   } else if (response.data instanceof Blob) {
      errorText = await response.data.text()
   }

   try {
      response.data = JSON.parse(errorText)
   } catch (e) {
      console.warn("Failed to parse binary JSON response:", e)
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