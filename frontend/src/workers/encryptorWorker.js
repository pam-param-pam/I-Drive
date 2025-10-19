import { encryptionMethod } from "@/utils/constants.js"
import JSChaCha20 from "js-chacha20"

function base64ToUint8Array(base64) {
   let binaryString = atob(base64)
   let len = binaryString.length
   let bytes = new Uint8Array(len)
   for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i)
   }
   return bytes
}

function incrementIV(iv, bytesToSkip) {
   if (bytesToSkip === 0) return iv

   let ivArray = new Uint8Array(iv)
   let blocksProcessed = Math.floor(bytesToSkip / 16)

   let counter =
      ((ivArray[12] << 24) |
         (ivArray[13] << 16) |
         (ivArray[14] << 8) |
         ivArray[15]) >>>
      0

   counter = (counter + blocksProcessed) >>> 0

   ivArray[12] = (counter >>> 24) & 0xff
   ivArray[13] = (counter >>> 16) & 0xff
   ivArray[14] = (counter >>> 8) & 0xff
   ivArray[15] = counter & 0xff

   return ivArray
}


function calculateCounter(bytesToSkip) {
   if (bytesToSkip === 0) {
      return 0
   }
   // ChaCha20 block size is 64 bytes
   return Math.floor(bytesToSkip / 64)

}


async function encryptWithAesCtr(arrayBuffer, base64Key, base64IV, bytesToSkip) {
   let key = base64ToUint8Array(base64Key)
   let iv = incrementIV(base64ToUint8Array(base64IV), bytesToSkip)

   let algorithm = { name: "AES-CTR", counter: iv, length: 64 }
   let cryptoKey = await crypto.subtle.importKey("raw", key, algorithm, false, ["encrypt"])
   let encryptedArrayBuffer = await crypto.subtle.encrypt(algorithm, cryptoKey, arrayBuffer)
   return new Uint8Array(encryptedArrayBuffer)
}


function encryptWithChaCha20(arrayBuffer, base64Key, base64IV, bytesToSkip) {
   let key = base64ToUint8Array(base64Key)
   let iv = base64ToUint8Array(base64IV)
   let counter = calculateCounter(bytesToSkip)

   return new JSChaCha20(key, iv, counter).encrypt(new Uint8Array(arrayBuffer))
}


// Worker message listener
self.onmessage = async function(e) {
   try {
      const { rawBlob, method, key, iv, bytesToSkip } = e.data
      let arrayBuffer = await rawBlob.arrayBuffer()
      let encrypted

      if (method === encryptionMethod.NotEncrypted) {
         encrypted = new Uint8Array(arrayBuffer)
      } else if (method === encryptionMethod.AesCtr) {
         encrypted = await encryptWithAesCtr(arrayBuffer, key, iv, bytesToSkip)
      } else if (method === encryptionMethod.ChaCha20) {
         encrypted = encryptWithChaCha20(arrayBuffer, key, iv, bytesToSkip)
      } else {
         throw new Error("Invalid encryption method")
      }
      self.postMessage({ encryptedBlob: new Blob([encrypted], { type: rawBlob.type }) })
   } catch (err) {
      self.postMessage({ error: err.message })
   }
}
