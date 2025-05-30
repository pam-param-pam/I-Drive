import JSChaCha20 from "js-chacha20"
import { attachmentType, encryptionMethod } from "@/utils/constants.js"

export function base64ToUint8Array(base64) {
   let binaryString = window.atob(base64)
   let len = binaryString.length
   let bytes = new Uint8Array(len)
   for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i)
   }
   return bytes
}

export async function encryptWithAesCtr(file, base64Key, base64IV, bytesToSkip) {

   let key = base64ToUint8Array(base64Key)
   let iv = base64ToUint8Array(base64IV)

   iv = incrementIV(iv, bytesToSkip)

   let algorithm = { name: "AES-CTR", counter: iv, length: 64 }
   let cryptoKey = await crypto.subtle.importKey(
      "raw",
      key,
      algorithm,
      false,
      ["encrypt"]
   )

   let arrayBuffer = await file.arrayBuffer()
   let encryptedArrayBuffer = await crypto.subtle.encrypt(
      algorithm,
      cryptoKey,
      arrayBuffer
   )

   return new Blob([new Uint8Array(encryptedArrayBuffer)], { type: file.type })
}

export async function encryptWithChaCha20(file, base64Key, base64IV, bytesToSkip) {

   let key = base64ToUint8Array(base64Key)
   let iv = base64ToUint8Array(base64IV)

   let counter = calculateCounter(bytesToSkip)
   let arrayBuffer = await file.arrayBuffer()

   let encryptedData = new JSChaCha20(key, iv, counter).encrypt(new Uint8Array(arrayBuffer))


   return new Blob([new Uint8Array(encryptedData)], { type: file.type })
}

// Calculate iv for AES CTR
function incrementIV(iv, bytesToSkip) {
   if (bytesToSkip === 0) {
      return iv
   }

   let ivArray = new Uint8Array(iv)

   // Calculate how many blocks have been processed
   let blocksProcessed = Math.floor(bytesToSkip / 16)

   // Extract current counter from the last 4 bytes
   let counter = (
      (ivArray[12] << 24) |
      (ivArray[13] << 16) |
      (ivArray[14] << 8) |
      ivArray[15]
   ) >>> 0 // Ensure it's treated as unsigned

   // Increment the counter by the number of blocks processed
   counter = (counter + blocksProcessed) >>> 0 // Ensure overflow wraps around

   // Update the last 4 bytes in the array with the new counter
   ivArray[12] = (counter >>> 24) & 0xff
   ivArray[13] = (counter >>> 16) & 0xff
   ivArray[14] = (counter >>> 8) & 0xff
   ivArray[15] = counter & 0xff

   return ivArray

}

// Calculate counter for ChaCha20
function calculateCounter(bytesToSkip) {
   if (bytesToSkip === 0) {
      return 0
   }
    // ChaCha20 block size is 64 bytes
   return Math.floor(bytesToSkip / 64)

}

export async function encryptAttachment(attachment) {
   let fileObj = attachment.fileObj

   let bytesToSkip = 0
   if (attachment.type === attachmentType.file) {
      bytesToSkip = attachment.offset
   }
   let iv = fileObj.iv
   let key = fileObj.key

   if (attachment.type === attachmentType.thumbnail) {
      iv = attachment.iv
      key = attachment.key
   }
   return await encrypt(attachment.rawBlob, fileObj.encryptionMethod, key, iv, bytesToSkip)

}

export async function encrypt(rawBlob, method, key, iv, bytesToSkip) {
   if (typeof rawBlob === "string") {
      rawBlob = new Blob([rawBlob])
   }

   if (method === encryptionMethod.NotEncrypted) {
      return rawBlob
   }

   if (method === encryptionMethod.ChaCha20) {
      return await encryptWithChaCha20(rawBlob, key, iv, bytesToSkip)

   } else if (method === encryptionMethod.AesCtr) {
      return await encryptWithAesCtr(rawBlob, key, iv, bytesToSkip)

   } else {
      console.warn("encrypt: invalid encryptionMethod: " + method)
   }


}