import axios from 'axios'
import {baseURL} from "@/utils/constants.js"
import vue from "@/utils/vue.js"
import store from "@/store/index.js"
import i18n from "@/i18n/index.js"
import {logout} from "@/utils/auth.js"

const cancelTokenMap = new Map()


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
      let retryAfter = error.response.headers['retry-after']

      if (retryAfter) {
        let waitTime = parseInt(retryAfter) * 1000 // Convert to milliseconds
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

  function(config) {

    if (cancelTokenMap.has(config.__cancelSignature)) {
      cancelTokenMap.get(config.__cancelSignature).cancel("Request cancelled due to a new request with the same cancel signature.")
    }
    // Create a new cancel token for the current request
    let cancelSource = axios.CancelToken.source()
    // Attach the cancel token to the request
    config.cancelToken = cancelSource.token
    // Store the cancel token in the map
    cancelTokenMap.set(config.__cancelSignature, cancelSource)

    let token = localStorage.getItem("token")
    if (token) {

      config.headers['Authorization'] = `Token ${token}`
    }

    return config

  },
  function(error) {
    return Promise.reject(error)
  }
)

backend_instance.interceptors.response.use(
  function(response) {
    //store.commit("setLoading", false)

    return response
  },
  async function(error) {
    if (axios.isCancel(error)) {
      return Promise.reject(error)

    }
    let { config, response } = error
    // Initialize retry counter if it doesn't exist
    if (!config.__retryCount) {
      config.__retryCount = 0
    }

    // Check if the error is 469 INCORRECT OR MISSING FOLDER PASSWORD
    if (response && response.status === 469) {
      if (config.__retryCount > 3) {
        store.commit("resetFolderPassword")
      }
      config.__retryCount++

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
            let password = store.getters.getFolderPassword(folder.id)
            if (password) {
              passwordExists.push({ id: folder.id, password: password })
            }
          })

          if (config.method === 'get') {
            config.headers = {
              ...config.headers,
              'X-folder-password': passwordExists[0]?.password || '', // Add the folder password to the headers
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
          let password = store.getters.getFolderPassword(folder.id)
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

            store.commit("showHover", {
              prompt: "FolderPassword",
              props: {requiredFolderPasswords: response.data.requiredFolderPasswords},
              confirm: () => {
                retry469Request(config)
                  .then(resolve)
                  .catch(reject)
              },
            })
          })
        }
        else {
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

      errorMessage = i18n.t("toasts.unauthorized")
      errorDetails = i18n.t("toasts.sessionExpired")
    }
    vue.$toast.error(`${errorMessage}\n${errorDetails}`, {
      timeout: 5000,
      position: "bottom-right",
    })
    // //we want to only catch not found errors
    // if (response.status === 404) {
    //   store.commit("setError", error)
    //   store.commit("setLoading", false)
    // }
    //

    // If not a 429 error, no Retry-After header, or max retries reached, just return the error
    return Promise.reject(error)
  }
)
