import axios from 'axios'
import {baseURL} from "@/utils/constants.js"
import vue from "@/utils/vue.js"
import store from "@/store/index.js"
import i18n from "@/i18n/index.js";
import {logout} from "@/utils/auth.js";


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

  function(response) {
    return response
  },
  function(error) {

    // Check if the error is 429 Too Many Requests errors
    if (error.response && error.response.status === 429) {
      const retryAfter = error.response.headers['retry-after']

      if (retryAfter) {
        const waitTime = parseInt(retryAfter) * 1000 // Convert to milliseconds
        console.log(`Received 429, retrying after ${waitTime} milliseconds.`)

        // Wait for the specified time before retrying the request
        return new Promise(function(resolve) {
          setTimeout(function() {
            resolve(discord_instance(error.config))
          }, waitTime)
        })
      }
    }
    if (!error.response && error.code === 'ERR_NETWORK') {

      function retry() {
        const delay = 5000 // waiting for 5 seconds cuz, I felt like it.
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

  function(config) {

    // Modify headers here
    config.headers['Authorization'] = `Token ${localStorage.getItem("token")}`
    return config
  },
  function(error) {
    return Promise.reject(error)
  }
)

backend_instance.interceptors.response.use(
  function(response) {
    return response
  },
  async function(error) {
    if (axios.isCancel(error)) {
      return Promise.reject(error)

    }
    const { config, response } = error




    // // Check if the error is 429 Too Many Requests error
    // if (response && response.status === 429) {
    //   const retryAfter = response.headers['retry-after']
    //   config.__retryCount = config.__retryCount || 0 // Initialize retry count if not already set
    //
    //   // If the retry count is less than 3
    //   if (config.__retryCount < 3) {
    //     config.__retryCount += 1 // Increment the retry count
    //
    //     if (retryAfter) {
    //       const waitTime = parseInt(retryAfter) * 1000 // Convert to milliseconds
    //       console.log(`Received 429, retrying after ${waitTime} milliseconds. Attempt ${config.__retryCount}`)
    //
    //       // Wait for the specified time before retrying the request
    //       return new Promise(function(resolve) {
    //         setTimeout(function() {
    //           resolve(backend_instance(config)) // Retry the request
    //         }, waitTime)
    //       })
    //     }
    //   }
    // }

    // Check if the error is 429 Too Many Requests error
    if (response && response.status === 469) {
      console.log(`Received 469`)
      const lockFrom = response.data.lockFrom
      if (lockFrom) {

        let password = store.getters.getFolderPassword(response.data.lockFrom)
        if (password) {
          config.headers = {
            ...config.headers,
            'X-folder-password': password, // Add the folder password to the headers
          }
          return new Promise(function(resolve) {
            resolve(backend_instance(config)) // Retry the request
          })
        }

        return new Promise((resolve, reject) => {

          store.commit("showHover", {
            prompt: "FolderPassword",
            props: {folderId: response.data.resourceId, lockFrom: lockFrom},
            cancel: () => {

              vue.$toast.error(i18n.t("toasts.passwordIsRequired"))


            },
            confirm: () => {
              console.log("confirm")
              let password = store.getters.getFolderPassword(response.data.lockFrom)

              config.headers = {
                ...config.headers,
                'X-folder-password': password, // Add the folder password to the headers
              }

              // Retry the request
              backend_instance(config)
                .then(resolve)  // Resolve the outer promise with the response
                .catch(reject) // Reject the outer promise with the error
            },
          })
        })
      }
    }
    let errorMessage = response.data.error
    let errorDetails = response.data.details
    if (!errorMessage && errorMessage !== "") errorMessage = "Unexpected error"
    if (!errorDetails && errorDetails !== "") errorDetails = "Report this"
    if (response.status === 401) {
      await logout()

      errorMessage = i18n.t("toasts.unauthorized")
      errorDetails = i18n.t("toasts.sessionExpired")
    }
    vue.$toast.error(`${errorMessage}\n${errorDetails}`, {
      timeout: 5000,
      position: "bottom-right",
    })
    // If not a 429 error, no Retry-After header, or max retries reached, just return the error
    return Promise.reject(error)
  }
)
