import { useMainStore } from "@/stores/mainStore.js"
import { watch } from "vue"
import { getFile } from "@/api/files.js"

async function handleServiceWorkerMessage(event) {
   const message = event.data

   if (message?.type === "SW_LOG") {
      return
      console.log("[SW LOGS] " + message.message)
      return
   }

   if (message?.type === "FILE_CONFIG_MISSING") {
      try {
         const file = await getFile(message.fileId)

         navigator.serviceWorker.controller?.postMessage({
            type: "FILE_CONFIG_MISSING_RESPONSE",
            requestId: message.requestId,
            file
         })
      } catch (error) {
         navigator.serviceWorker.controller?.postMessage({
            type: "FILE_CONFIG_MISSING_RESPONSE",
            requestId: message.requestId,
            error: error.message || String(error)
         })
      }
   }
}


let stopFileConfigSync = null

export function startFileConfigServiceWorkerSync(pinia) {
   if (stopFileConfigSync) return

   const mainStore = useMainStore(pinia)

   stopFileConfigSync = watch(
      () => mainStore.sortedItems,
      async items => {
         await registerFileConfigsInServiceWorker(items)
      },
      { immediate: true, flush: "post" }
   )
}

function waitForServiceWorkerActivation(registration) {
   const worker = registration.installing || registration.waiting || registration.active

   if (!worker) {
      return Promise.resolve()
   }

   if (worker.state === "activated") {
      return Promise.resolve()
   }

   return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
         worker.removeEventListener("statechange", onStateChange)
         reject(new Error("Timed out waiting for service worker activation"))
      }, 1000)

      function onStateChange() {
         if (worker.state === "activated") {
            clearTimeout(timeoutId)
            worker.removeEventListener("statechange", onStateChange)
            resolve()
         }
      }

      worker.addEventListener("statechange", onStateChange)
   })
}

function waitForServiceWorkerController() {
   if (navigator.serviceWorker.controller) {
      return Promise.resolve()
   }

   return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
         navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange)
         reject(new Error("Timed out waiting for service worker controller"))
      }, 500)

      function onControllerChange() {
         clearTimeout(timeoutId)
         navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange)
         resolve()
      }

      navigator.serviceWorker.addEventListener("controllerchange", onControllerChange)
   })
}

function pingServiceWorker() {
   const controller = navigator.serviceWorker.controller

   if (!controller) {
      throw new Error("No active service worker controller")
   }

   const requestId = crypto.randomUUID()

   return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
         navigator.serviceWorker.removeEventListener("message", onMessage)
         reject(new Error("Timed out waiting for service worker PONG"))
      }, 5000)

      function onMessage(event) {
         const message = event.data

         if (message?.type !== "SW_PONG" || message.requestId !== requestId) {
            return
         }

         clearTimeout(timeoutId)
         navigator.serviceWorker.removeEventListener("message", onMessage)
         resolve()
      }

      navigator.serviceWorker.addEventListener("message", onMessage)

      controller.postMessage({
         type: "SW_PING",
         requestId
      })
   })
}

export async function initServiceWorker() {
   if (!("serviceWorker" in navigator)) {
      throw new Error("Service workers are not supported")
   }

   navigator.serviceWorker.addEventListener("message", handleServiceWorkerMessage)

   const registration = await navigator.serviceWorker.register("/service_worker.js", {
      scope: "/",
      type: "module"
   })

   await waitForServiceWorkerActivation(registration)
   await waitForServiceWorkerController()
   await pingServiceWorker()

   return registration
}


export function waitForServiceWorkerAck(requestId) {
   return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
         navigator.serviceWorker.removeEventListener("message", onMessage)
         reject(new Error("Timed out waiting for service worker ACK"))
      }, 3000)


      function onMessage(event) {
         if (event.data?.type !== "ACK") {
            return
         }

         if (event.data.requestId !== requestId) {
            return
         }

         clearTimeout(timeout)
         navigator.serviceWorker.removeEventListener("message", onMessage)
         resolve()
      }


      navigator.serviceWorker.addEventListener("message", onMessage)
   })
}


export async function registerFileConfigsInServiceWorker(files) {
   const registration = await navigator.serviceWorker.ready
   const sw = registration.active || navigator.serviceWorker.controller

   if (!sw) {
      throw new Error("No active service worker")
   }

   const requestId = crypto.randomUUID()

   sw.postMessage({
      requestId,
      type: "REGISTER_FILE_CONFIGS",
      files: files
   })

   await waitForServiceWorkerAck(requestId)
}