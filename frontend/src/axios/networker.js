import axios from "axios"
import { baseURL } from "@/utils/constants.js"
import i18n from "@/i18n/index.js"
import { useMainStore } from "@/stores/mainStore.js"
import { useToast } from "vue-toastification"
import { displayErrorToastIfNeeded, noWifi, shouldRetry469 } from "@/axios/helper.js"
import { retry469Error, retryRequest } from "@/axios/retry.js"
import { attachCancelSignature, parseBinaryJsonResponse } from "@/axios/helper.js"

const toast = useToast()
let upload_429_errors = 0

export const backendInstance = axios.create({
   baseURL: baseURL,
   timeout: 20000,
   headers: {
      "Content-Type": "application/json"
   }
})

export const uploadInstance = axios.create({
   timeout: null,
   headers: { "Content-Type": "multipart/form-data" }
})

uploadInstance.interceptors.response.use(
   function(response) {
      upload_429_errors = Math.max(upload_429_errors - 1, 0)
      return response
   },
   function(error) {
      if (error?.config?.onErrorCallback) error.config.onErrorCallback(error)
      const mainStore = useMainStore()

      if (upload_429_errors > 4) {
         upload_429_errors = - 10
         toast.warning(`${i18n.global.t('toasts.ALotOF429')}\n${i18n.global.t('toasts.ALotOF429Explained')}`, {
            timeout: 10000,
            position: "bottom-right"
         })
         if (mainStore.settings.concurrentUploadRequests > 6) {
            mainStore.settings.concurrentUploadRequests = 4
         } else {
            mainStore.settings.concurrentUploadRequests = 2
         }

      }

      // Check if the error is 429 Too Many Requests errors
      if (error.response && error.response.status === 429) {
         upload_429_errors++
         let retryAfter = error.response.headers["x-ratelimit-reset-after"]
         if (retryAfter) {
            retryAfter = parseInt(retryAfter) * 1000
         }
         retryAfter = retryAfter || 0
         console.log(`Received 429, retrying after ${retryAfter} milliseconds.`)
         return retryRequest(uploadInstance, error, retryAfter)

      } else if (noWifi(error)) {
         return retryRequest(uploadInstance, error, 1500, 1)
      }
      //handle discord fucking itself up
      else if (error.response && error.response.status >= 500) {
         return retryRequest(uploadInstance, error, 5000)
      }

      //else just return the error
      return Promise.reject(error)
   }
)

backendInstance.interceptors.request.use(
   function(config) {
      attachCancelSignature(config)
      let token = localStorage.getItem("token")
      if (token && !config.headers["Authorization"]) {
         config.headers["Authorization"] = `Token ${token}`
      }
      return config
   },
   function(error) {
      return Promise.reject(error)
   }
)

backendInstance.interceptors.response.use(
   function(response) {
      return response
   },
   async function(error) {
      let { config, response } = error
      await parseBinaryJsonResponse(response, config)

      //Handle cancelled request
      if (axios.isCancel(error)) {
         return Promise.reject(error)
      }

      //Handle 469
      if (shouldRetry469(error)) {
         console.warn(`Received 469, retrying.`)
         return retry469Error(backendInstance, error)
      }

      //Handle 429
      if (response && response.status === 429 && error.config.__retryErrors) {
         let retryAfter = error.response.headers["retry-after"]
         if (retryAfter) {
            let waitTime = parseInt(retryAfter) * 1000
            console.warn(`Received 429, retrying after ${waitTime} milliseconds.`)
            return retryRequest(backendInstance, error, waitTime)
         }
      }

      //Handle No Wi-Fi
      if (noWifi(error) && error.config.__retryErrors) {
         console.warn(`No WIFI, retrying after 5 seconds.`)
         return retryRequest(backendInstance, error, 5000)
      }

      //Handle 5XX
      if (response?.status >= 500 && error.config.__retryErrors) {
         console.warn(`Received 5XX, retrying after 1 second.`)
         return retryRequest(backendInstance, error, 1000)
      }

      await displayErrorToastIfNeeded(error)

      return Promise.reject(error)
   }
)
