import { backendInstance } from "@/axios/networker.js"
import { useMainStore } from "@/stores/mainStore.js"

export async function retryRequest(instance, error, delay, maxRetries = 5) {
   const config = error.config

   if (!config) return Promise.reject(error)

   if (!error.config.__retryCount) { error.config.__retryCount = 0 }

   if (config.__retryCount >= maxRetries) {
      console.warn(`Max retries reached (${maxRetries}). Aborting.`)
      return Promise.reject(error)
   }

   config.__retryCount++

   console.log(`Retrying request in ${delay}ms (attempt #${config.__retryCount} of ${maxRetries})`)

   await new Promise(resolve => setTimeout(resolve, delay))

   return instance(config)
}


export async function retry469Error(instance, error, maxTries=2) {
   const mainStore = useMainStore()
   let config = error.config
   if (!config.__retryCount) config.__retryCount = 0
   if (config.__retryCount > maxTries) return Promise.reject(error)

   config.__retryCount++

   //Reset cached passwords in case we have outdated cached ones to not end up in an infinite loop
   if (config.__469Retried) {
      mainStore.resetFolderPassword()
   }
   config.__469Retried = true

   let requiredFolderPasswords = error.response.data.requiredFolderPasswords

   let passwordExists = []
   let passwordMissing = []

   function retry469Request() {
      return new Promise((resolve, reject) => {
         // Ensure config.data is an object and not a parsed JSON into a string
         if (typeof config.data === "string") {
            config.data = JSON.parse(config.data)
         }

         passwordMissing.forEach(folder => {
            let password = mainStore.getFolderPassword(folder.id)
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
      error.response.data.requiredFolderPasswords.forEach(folder => {
         let password = mainStore.getFolderPassword(folder.id)
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
            mainStore.showHover({
               prompt: "FolderPassword",
               props: { requiredFolderPasswords: error.response.data.requiredFolderPasswords, isInShareContext: config.__shareContext },
               confirm: () => {
                  console.log("on confirm")
                  retry469Request(config)
                     .then(resolve)
                     .catch(reject)
               },
               cancel: () => {
                  console.log("on cancel")
                  reject(error)
               },
            })
         })
      } else {
         return retry469Request()
      }
   }
}