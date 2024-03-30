import axios from 'axios';
import store from "@/store/index.js";
import {baseURL} from "@/utils/constants.js";
// Function to calculate the delay using exponential backoff strategy

const backend_instance = axios.create({
  baseURL: baseURL,
  timeout: 1000,
  headers: {
    "Authorization": `Token ${localStorage.getItem("token")}`,
    "Content-Type": "application/json",
  },
});

const discord_instance = axios.create({
  headers: {
    "Content-Type": "application/json",
  },
});
// Add a response interceptor
discord_instance.interceptors.response.use(
  function(response) {
    return response;
  },
  function(error) {
    // Check if the error is 429 Too Many Requests errors
    if (error.response && error.response.status === 429) {
      const retryAfter = error.response.headers['retry-after'];

      if (retryAfter) {
        const waitTime = parseInt(retryAfter) * 1000; // Convert to milliseconds
        console.log(`Received 429, retrying after ${waitTime} milliseconds.`);

        // Wait for the specified time before retrying the request
        return new Promise(function(resolve) {
          setTimeout(function() {
            resolve(discord_instance(error.config));
          }, waitTime);
        });
      }
    }
    if (!error.response && error.code === 'ERR_NETWORK') {

      function retry() {
        const delay = 5000 // waiting for 5 seconds cuz, I felt like it.
        console.log(`Retrying request after ${delay} milliseconds`);
        return new Promise(resolve => setTimeout(resolve, delay)).then(() => discord_instance(error.config));
      }

      return retry();

    }

      // If not a 429 error or no Retry-After header, just return the error
    return Promise.reject(error);
  }
);