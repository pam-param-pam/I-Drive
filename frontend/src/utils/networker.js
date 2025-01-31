import axios from "axios"
import { baseURL } from "@/utils/constants.js"
import i18n from "@/i18n/index.js"
import { logout } from "@/utils/auth.js"
import { useMainStore } from "@/stores/mainStore.js"
import { useToast } from "vue-toastification"
import { useUploadStore } from "@/stores/uploadStore.js"

const toast = useToast()

const cancelTokenMap = new Map()
function retry(error, delay, retries = 0, maxRetries = 5) {
   if (retries >= maxRetries) {
      console.error(`Max retries reached: ${maxRetries}. Aborting.`);
      return Promise.reject(error);
   }

   console.log(`Retrying request after ${delay} milliseconds. Attempt #${retries + 1} of ${maxRetries}`);
   return new Promise(resolve => setTimeout(resolve, delay))
      .then(() => discordInstance(error.config))
      .catch(err => {
         console.error(`Retry attempt #${retries + 1} failed with error: ${err.message}`);
         return retry(error, delay, retries + 1, maxRetries);
      });
}

export const backendInstance = axios.create({
   baseURL: baseURL,
   timeout: 20000,
   headers: {
      "Content-Type": "application/json"
   }
})

export const discordInstance = axios.create({
   headers: {
      "Content-Type": "application/json"
   }
})


// Add a response interceptor
discordInstance.interceptors.response.use(
   function(response) {
      const uploadStore = useUploadStore()
      uploadStore.isInternet = true
      return response
   },
   function(error) {
      if (error.config.onErrorCallback) error.config.onErrorCallback()

      // Check if the error is 429 Too Many Requests errors
      if (error.response && error.response.status === 429) {
         let retryAfter = error.response.headers["x-ratelimit-reset-after"]
         if (retryAfter) {
            let waitTime = parseInt(retryAfter) * 1000 // Convert to milliseconds
            console.log(`Received 429, retrying after ${waitTime} milliseconds.`)
            return retry(error, waitTime)
         }
      }
      if ((!error.response && error.code === "ERR_NETWORK") || error.response && error.response.status === 502) {
         // no internet!
         const uploadStore = useUploadStore()
         uploadStore.isInternet = false
         return retry(error, 5000)
      }

      // If not a 429 error or no Retry-After header, just return the error
      return Promise.reject(error)
   }
)

backendInstance.interceptors.request.use(
   function(config) {

      if (config.__cancelSignature !== undefined && cancelTokenMap.has(config.__cancelSignature)) {
         cancelTokenMap.get(config.__cancelSignature).cancel(`Request cancelled due to a new request with the same cancel signature (${config.__cancelSignature}).`)
      }
      // Create a new cancel token for the current request
      let cancelSource = axios.CancelToken.source()
      // Attach the cancel token to the request
      config.cancelToken = cancelSource.token
      // Store the cancel token in the map
      cancelTokenMap.set(config.__cancelSignature, cancelSource)

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
      //store.commit("setLoading", false)
      const uploadStore = useUploadStore()
      uploadStore.isInternet = true
      return response
   },
   async function(error) {
      let { config, response } = error

      const store = useMainStore()
      console.warn("ON REJECTED")

      if (axios.isCancel(error)) {
         return Promise.reject(error)

      }
      // Check if the error is 429 Too Many Requests errors
      if (response && response.status === 429 && error.config.__retry500) {
         let retryAfter = error.response.headers["retry-after"]
         if (retryAfter) {
            let waitTime = parseInt(retryAfter) * 1000 // Convert to milliseconds
            console.warn(`Received 429, retrying after ${waitTime} milliseconds.`)
            return retry(error, waitTime)
         }
      }
      if ((!response && error.code === "ERR_NETWORK") || response && response.status === 502) {
         // no internet!
         const uploadStore = useUploadStore()
         uploadStore.isInternet = false
         return retry(error, 5000)
      }


      if (response && response.status === 500 && config.__retry500) {
         console.warn(`Received 500, retrying after 1 seconds.`)
         return retry(error, 1000)
      }

      if (!config.__retryCount) {
         config.__retryCount = 0
      }
      if (config.__retryCount > 3) {
         return Promise.reject(error)
      }
      config.__retryCount++

      // Check if the error is 469 INCORRECT OR MISSING FOLDER PASSWORD
      if (response && response.status === 469 && (config.__manage469 === true || config.__manage469 === undefined)) {

         //Reset cached passwords in case we have outdated cached ones to not end up in an infinite loop
         if (config.__469Retried) {
            store.resetFolderPassword()
         }
         config.__469Retried = true

         let requiredFolderPasswords = response.data.requiredFolderPasswords

         let passwordExists = []
         let passwordMissing = []

         function retry469Request() {
            return new Promise((resolve, reject) => {
               // Ensure config.data is an object and not a parsed JSON into a string
               if (typeof config.data === "string") {
                  config.data = JSON.parse(config.data)
               }

               passwordMissing.forEach(folder => {
                  let password = store.getFolderPassword(folder.id)
                  if (password) {
                     passwordExists.push({ id: folder.id, password: password })
                  }
               })

               if (config.method === "get") {
                  config.headers = {
                     ...config.headers,
                     "X-resource-password": passwordExists[0]?.password || ""
                  }
               } else {
                  config.data.resourcePasswords = {}
                  passwordExists.forEach(folder => {
                     let folder_id = folder.id
                     config.data.resourcePasswords[folder_id] = folder.password
                  })

               }
               // Retry the request
               backendInstance(config)
                  .then(resolve) // Resolve the outer promise with the response
                  .catch(reject) // Reject the outer promise with the error
            })
         }

         if (requiredFolderPasswords) {

            // Iterate through requiredFolderPasswords
            response.data.requiredFolderPasswords.forEach(folder => {
               let password = store.getFolderPassword(folder.id)
               if (password) {
                  // Password exists in cache
                  passwordExists.push({ id: folder.id, password: password })
               } else {
                  // Password does not exist in cache
                  passwordMissing.push({ id: folder.id, name: folder.name })
               }
            })

            if (passwordMissing.length > 0) {
               return new Promise((resolve, reject) => {

                  store.showHover({
                     prompt: "FolderPassword",
                     props: { requiredFolderPasswords: response.data.requiredFolderPasswords },
                     confirm: () => {
                        retry469Request(config)
                           .then(resolve)
                           .catch(reject)
                     }
                  })
               })
            } else {
               return retry469Request()
            }
         }
      }
      let errorMessage = response.data.error
      let errorDetails = response.data.details
      if (!errorMessage && errorMessage !== "") errorMessage = "Unexpected error"
      if (!errorDetails && errorDetails !== "") errorDetails = "Report this"
      if (response.status === 401) {
         await logout()

         errorMessage = i18n.global.t("toasts.unauthorized")
         errorDetails = i18n.global.t("toasts.sessionExpired")
      }
      if (config.__displayErrorToast !== false) {
         toast.error(`${i18n.global.t(errorMessage)}\n${i18n.global.t(errorDetails)}`, {
            timeout: 5000,
            position: "bottom-right"
         })
      }


      // If not a 469 error, just return the error
      return Promise.reject(error)
   }
)
