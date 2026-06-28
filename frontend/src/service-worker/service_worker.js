import { decryptAesCtr, decryptChaCha20CryptographyCompatible } from "../utils/crypto/decryption.js"


const FILE_CONFIGS = new Map()
const PENDING_FILE_CONFIG_REQUESTS = new Map()
const FILE_CONFIG_MISSING_TIMEOUT_MS = 5000


export function addToFileConfig(file) {
   FILE_CONFIGS.set(file.id, {
      id: file.id,
      method: file.encryption_method,
      backendUrl: file.download_url + "&raw=True",
      keyBase64: file.key,
      ivBase64: file.iv
   })
}


self.addEventListener("message", event => {
   const message = event.data

   if (message?.type === "SW_PING") {
      event.source?.postMessage({
         type: "SW_PONG",
         requestId: message.requestId
      })
      return
   }

   if (message?.type === "REGISTER_FILE_CONFIGS") {
      const { requestId, files = [] } = message

      for (const file of files) {
         addToFileConfig(file)
         resolvePendingFileConfigRequestByFileId(file.id, file)
      }

      event.source?.postMessage({
         type: "ACK",
         requestId
      })

      logToClients(`Registered ${files.length} file configs`)
      return
   }

   if (message?.type === "FILE_CONFIG_MISSING_RESPONSE") {
      const { requestId, file, error } = message
      const pending = PENDING_FILE_CONFIG_REQUESTS.get(requestId)

      if (!pending) {
         return
      }

      clearTimeout(pending.timeoutId)
      PENDING_FILE_CONFIG_REQUESTS.delete(requestId)

      if (error) {
         pending.reject(new Error(error))
         return
      }

      if (!file) {
         pending.reject(new Error(`Missing file config response body for fileId=${pending.fileId}`))
         return
      }

      addToFileConfig(file)
      pending.resolve(file)
   }
})


self.addEventListener("install", event => {
   logToClients("SW install")
   self.skipWaiting()
})


self.addEventListener("activate", event => {
   logToClients("SW activate")
   event.waitUntil(self.clients.claim())
})


self.addEventListener("fetch", event => {
   const url = new URL(event.request.url)

   if (!url.pathname.startsWith("/raw-file/")) {
      return
   }

   event.respondWith(handleVideoRequest(event.request, url, event.clientId))
})


function createDecryptingStream(fileConfig, initialOffset) {
   let currentOffset = initialOffset

   return new TransformStream({
      async transform(chunk, controller) {
         const encryptedBytes = chunk instanceof Uint8Array ? chunk : new Uint8Array(chunk)
         let decryptedBytes

         if (fileConfig.method === 1) {
            decryptedBytes = await decryptAesCtr(encryptedBytes, fileConfig.keyBase64, fileConfig.ivBase64, currentOffset)
         } else if (fileConfig.method === 2) {
            decryptedBytes = decryptChaCha20CryptographyCompatible(encryptedBytes, fileConfig.keyBase64, fileConfig.ivBase64, currentOffset)
         } else {
            throw new Error(`Unsupported method: ${fileConfig.method}`)
         }

         currentOffset += encryptedBytes.byteLength
         controller.enqueue(decryptedBytes)
      }
   })
}


async function handleVideoRequest(request, url, clientId) {
   try {
      const fileId = url.pathname.split("/")[2]
      let fileConfig = FILE_CONFIGS.get(fileId)

      if (!fileConfig) {
         logToClients(`No file config registered for fileId=${fileId}; requesting from client`)

         try {
            fileConfig = await requestMissingFileConfig(fileId, clientId, FILE_CONFIG_MISSING_TIMEOUT_MS)
         } catch (error) {
            logToClients(`Failed to obtain file config for fileId=${fileId}: ${error.message}`)
            return formatError(404, "errors.swNoFileConfigDetails")
         }
      }

      const rangeHeader = request.headers.get("Range")
      const startByte = parseRangeStart(rangeHeader)

      logToClients(`Intercepted ${request.method} ${url.pathname}`)
      logToClients(`Range: ${rangeHeader || "none"}`)
      logToClients(`Start byte: ${startByte}`)

      const backendHeaders = new Headers()

      if (rangeHeader) {
         backendHeaders.set("Range", rangeHeader)
      }

      const backendResponse = await fetchWithTimeout(fileConfig.backendUrl, {
         method: "GET",
         headers: backendHeaders,
         credentials: "omit",
         cache: "no-store",
         mode: "cors"
      }, 10000)

      logToClients(`Backend response: ${backendResponse.status} ${backendResponse.statusText}`)
      logToClients(`Backend Content-Type: ${backendResponse.headers.get("Content-Type")}`)
      logToClients(`Backend Content-Length: ${backendResponse.headers.get("Content-Length")}`)
      logToClients(`Backend Content-Range: ${backendResponse.headers.get("Content-Range")}`)

      if (!backendResponse.body) {
         throw new Error("Backend response has no body")
      }

      if (!backendResponse.ok && backendResponse.status !== 206) {
         return backendResponse
      }

      if (fileConfig.method === 0) {
         logToClients("No decryption used")
         return backendResponse
      }

      const responseHeaders = copyUsefulHeaders(backendResponse.headers)
      responseHeaders.set("Accept-Ranges", "bytes")

      const decryptedStream = createDecryptingStream(fileConfig, startByte)

      return new Response(backendResponse.body.pipeThrough(decryptedStream), {
         status: backendResponse.status,
         statusText: backendResponse.statusText,
         headers: responseHeaders
      })
   } catch (err) {
      logToClients(`SW failed: ${err.message}`)
      return formatError(502, `Service Worker failed: ${err.message}`)
   }
}


async function requestMissingFileConfig(fileId, clientId, timeoutMs) {
   const existingConfig = FILE_CONFIGS.get(fileId)

   if (existingConfig) {
      return existingConfig
   }

   const requestId = createRequestId()

   const promise = new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
         PENDING_FILE_CONFIG_REQUESTS.delete(requestId)
         reject(new Error(`Timed out waiting for file config: fileId=${fileId}`))
      }, timeoutMs)

      PENDING_FILE_CONFIG_REQUESTS.set(requestId, {
         fileId,
         resolve,
         reject,
         timeoutId
      })
   })

   const sent = await sendFileConfigMissingMessage(fileId, clientId, requestId)

   if (!sent) {
      const pending = PENDING_FILE_CONFIG_REQUESTS.get(requestId)

      if (pending) {
         clearTimeout(pending.timeoutId)
         PENDING_FILE_CONFIG_REQUESTS.delete(requestId)
      }

      throw new Error(`No client available to provide file config: fileId=${fileId}`)
   }

   await promise

   const fileConfig = FILE_CONFIGS.get(fileId)

   if (!fileConfig) {
      throw new Error(`Client responded, but FILE_CONFIGS is still missing fileId=${fileId}`)
   }

   return fileConfig
}


async function sendFileConfigMissingMessage(fileId, clientId, requestId) {
   const message = {
      type: "FILE_CONFIG_MISSING",
      requestId,
      fileId
   }

   if (clientId) {
      const client = await self.clients.get(clientId)

      if (client) {
         client.postMessage(message)
         return true
      }
   }

   const clients = await self.clients.matchAll({
      includeUncontrolled: true,
      type: "window"
   })

   for (const client of clients) {
      client.postMessage(message)
   }

   return clients.length > 0
}


function resolvePendingFileConfigRequestByFileId(fileId, file) {
   for (const [requestId, pending] of PENDING_FILE_CONFIG_REQUESTS.entries()) {
      if (pending.fileId !== fileId) {
         continue
      }

      clearTimeout(pending.timeoutId)
      PENDING_FILE_CONFIG_REQUESTS.delete(requestId)
      pending.resolve(file)
   }
}


function createRequestId() {
   if (crypto.randomUUID) {
      return crypto.randomUUID()
   }

   return `${Date.now()}-${Math.random()}`
}


async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
   const controller = new AbortController()
   const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

   try {
      return await fetch(url, {
         ...options,
         signal: controller.signal
      })
   } finally {
      clearTimeout(timeoutId)
   }
}


function formatError(status, details) {
   return new Response(JSON.stringify({
      error: "errors.serviceWorkerError",
      details
   }), {
      status,
      headers: {
         "Content-Type": "application/json"
      }
   })
}


function parseRangeStart(rangeHeader) {
   if (!rangeHeader) {
      return 0
   }

   const match = rangeHeader.match(/^bytes=(\d+)-/)

   if (!match) {
      return 0
   }

   return Number(match[1])
}


function copyUsefulHeaders(sourceHeaders) {
   const headers = new Headers()

   for (const name of ["Content-Type", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified", "Content-Disposition", "Content-Length"]) {
      const value = sourceHeaders.get(name)

      if (value !== null) {
         headers.set(name, value)
      }
   }

   return headers
}


async function logToClients(message) {
   const clients = await self.clients.matchAll({
      includeUncontrolled: true,
      type: "window"
   })

   for (const client of clients) {
      client.postMessage({
         type: "SW_LOG",
         message,
         time: new Date().toISOString()
      })
   }
}