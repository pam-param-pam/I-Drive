import axios from 'axios'
import {baseURL} from "@/utils/constants.js"
import i18n from "@/i18n/index.js"
import {logout} from "@/utils/auth.js"
import {useMainStore} from "@/stores/mainStore.js"
import {useToast} from "vue-toastification"
import {useUploadStore} from "@/stores/uploadStore.js";

const toast = useToast()

const cancelTokenMap = new Map()

//todo handle backends 429 policy lel
export const backend_instance = axios.create({
   baseURL: baseURL,
   timeout: 20000,
   headers: {
      "Content-Type": "application/json",
   },
})

export const discord_instance = axios.create({
   headers: {
      "Content-Type": "application/json",
   },
})






// Add a response interceptor
discord_instance.interceptors.response.use(
   function (response) {
      const uploadStore = useUploadStore()
      uploadStore.isInternet = true
      return response
   },
   function (error) {

      // Check if the error is 429 Too Many Requests errors
      if (error.response && error.response.status === 429) {
         let retryAfter = error.response.headers['retry-after']

         if (retryAfter) {
            let waitTime = parseInt(retryAfter) * 1000 // Convert to milliseconds
            console.log(`Received 429, retrying after ${waitTime} milliseconds.`)

            // Wait for the specified time before retrying the request
            return new Promise(function (resolve) {
               setTimeout(function () {
                  resolve(discord_instance(error.config))
               }, waitTime)
            })
         }
      }
      if ((!error.response && error.code === 'ERR_NETWORK') || error.code === 502) {
         // no internet!
         const uploadStore = useUploadStore()
         uploadStore.isInternet = false

         function retry() {
            let delay = 5000 // waiting for 5 seconds cuz, I felt like it.
            console.log(`Retrying request after ${delay} milliseconds`)
            return new Promise(resolve => setTimeout(resolve, delay)).then(() => discord_instance(error.config))
         }

         return retry()
      }

      // If not a 429 error or no Retry-After header, just return the error
      return Promise.reject(error)
   }
)

backend_instance.interceptors.request.use(
   function (config) {

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
      if (token) { //todo check if config.headers['Authorization'] is not set to False

         config.headers['Authorization'] = `Token ${token}`
      }

      return config

   },
   function (error) {
      return Promise.reject(error)
   }
)

backend_instance.interceptors.response.use(
   function (response) {
      //store.commit("setLoading", false)
      const uploadStore = useUploadStore()
      uploadStore.isInternet = true
      return response
   },
   async function (error) {

      const store = useMainStore()
      console.log("ON REJECTED")

      if (axios.isCancel(error)) {
         return Promise.reject(error)

      }
      if ((!error.response && error.code === 'ERR_NETWORK') || error.code === 502) {
         // no internet!
         const uploadStore = useUploadStore()
         uploadStore.isInternet = false
         function retry() {
            let delay = 5000 // waiting for 5 seconds cuz, I felt like it.
            console.log(`Retrying request after ${delay} milliseconds`)
            return new Promise(resolve => setTimeout(resolve, delay)).then(() => discord_instance(error.config))
         }

         return retry()
      }

      let {config, response} = error

      // Check if the error is 469 INCORRECT OR MISSING FOLDER PASSWORD
      if (response && response.status === 469) {

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
               if (typeof config.data === 'string') {
                  config.data = JSON.parse(config.data)
               }

               passwordMissing.forEach(folder => {
                  let password = store.getFolderPassword(folder.id)
                  if (password) {
                     passwordExists.push({id: folder.id, password: password})
                  }
               })

               if (config.method === 'get') {
                  config.headers = {
                     ...config.headers,
                     'X-resource-password': passwordExists[0]?.password || '',
                  }
               } else {
                  config.data.resourcePasswords = {}
                  passwordExists.forEach(folder => {
                     let folder_id = folder.id
                     config.data.resourcePasswords[folder_id] = folder.password
                  })

               }
               // Retry the request
               backend_instance(config)
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
                  passwordExists.push({id: folder.id, password: password})
               } else {
                  // Password does not exist in cache
                  passwordMissing.push({id: folder.id, name: folder.name})
               }
            })

            if (passwordMissing.length > 0) {
               return new Promise((resolve, reject) => {

                  store.showHover({
                     prompt: "FolderPassword",
                     props: {requiredFolderPasswords: response.data.requiredFolderPasswords},
                     confirm: () => {
                        retry469Request(config)
                           .then(resolve)
                           .catch(reject)
                     },
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
         toast.error(`${i18n.global.t(errorMessage)}\n${errorDetails}`, {
            timeout: 5000,
            position: "bottom-right",
         })
      }


      // If not a 469 error, just return the error
      return Promise.reject(error)
   }
)
