import { prepareRequests } from "@/utils/upload.js"

self.onmessage = async (event) => {
   const { action, data } = event.data

   if (action === "generateRequests") {
      // Assuming prepareRequests() is a function that generates the requests
      const requests = await prepareRequests()
      postMessage({ action: "requestsGenerated", data: requests })
   }
}
