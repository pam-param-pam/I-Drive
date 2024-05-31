import axios from 'axios'
import {baseURL} from "@/utils/constants.js"
import vue from "@/utils/vue.js";
import {CONFIGURABLE} from "core-js/internals/function-name.js";
// Function to calculate the delay using exponential backoff strategy

export const backend_instance = axios.create({
  baseURL: baseURL,
  timeout: 20000,
  headers: {
    "Authorization": `Token ${localStorage.getItem("token")}`,
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


backend_instance.interceptors.response.use(
  function(response) {
    return response;
  },
  async function(error) {
    const { config, response } = error;

    let errorMessage = response.data.error
    let errorDetails = response.data.details

    vue.$toast.error(`${errorMessage}\n${errorDetails}`, {
      timeout: 5000,
      position: "bottom-right",
    })
    // // Check if the error is 429 Too Many Requests error
    // if (response && response.status === 429) {
    //   const retryAfter = response.headers['retry-after'];
    //   config.__retryCount = config.__retryCount || 0; // Initialize retry count if not already set
    //
    //   // If the retry count is less than 3
    //   if (config.__retryCount < 3) {
    //     config.__retryCount += 1; // Increment the retry count
    //
    //     if (retryAfter) {
    //       const waitTime = parseInt(retryAfter) * 1000; // Convert to milliseconds
    //       console.log(`Received 429, retrying after ${waitTime} milliseconds. Attempt ${config.__retryCount}`);
    //
    //       // Wait for the specified time before retrying the request
    //       return new Promise(function(resolve) {
    //         setTimeout(function() {
    //           resolve(backend_instance(config)); // Retry the request
    //         }, waitTime);
    //       });
    //     }
    //   }
    // }

    // If not a 429 error, no Retry-After header, or max retries reached, just return the error
    return Promise.reject(error);
  }
);
