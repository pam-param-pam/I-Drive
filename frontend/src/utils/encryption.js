import JSChaCha20 from "js-chacha20"
import {attachmentType, chunkSize, encryptionMethod} from "@/utils/constants.js"

function base64ToUint8Array(base64) {
   let binaryString = window.atob(base64)
   let len = binaryString.length
   let bytes = new Uint8Array(len)
   for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i)
   }
   return bytes
}

export async function encryptWithAesCtr(base64Key, base64IV, file) {

   let key = base64ToUint8Array(base64Key)
   let iv = base64ToUint8Array(base64IV)

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
      { name: "AES-CTR", counter: iv, length: 64 },
      cryptoKey,
      arrayBuffer
   )

   return new Blob([new Uint8Array(encryptedArrayBuffer)], { type: file.type })
}

export async function encryptWithChaCha20(base64Key, base64IV, file) {

   let key = base64ToUint8Array(base64Key)
   let iv = base64ToUint8Array(base64IV)

   let arrayBuffer = await file.arrayBuffer()

   let encryptedData = new JSChaCha20(key, iv).encrypt(new Uint8Array(arrayBuffer))


   return new Blob([new Uint8Array(encryptedData)], { type: file.type })
}

// AES Counter (CTR) Helper for IV Increment
function incrementIV(iv, bytesToSkip) {
   const blocksToSkip = Math.floor(bytesToSkip / 16) // AES block size is 16 bytes
   const ivArray = new Uint8Array(iv)

   // Increment the IV by the number of blocks to skip
   for (let i = ivArray.length - 1; i >= 0; i--) {
      const increment = blocksToSkip % 256
      const newByte = ivArray[i] + increment
      ivArray[i] = newByte % 256
      if (newByte < 256) break
   }

   return ivArray
}

// ChaCha20 Nonce Calculation
function calculateNonce(iv, bytesToSkip) {
   const blocksToSkip = Math.floor(bytesToSkip / 64) // ChaCha20 block size is 64 bytes
   const nonceArray = new Uint8Array(iv)

   // Update only the first 4 bytes of nonce with the incremented counter
   for (let i = 0; i < 4; i++) {
      const increment = blocksToSkip % 256
      const newByte = nonceArray[i] + increment
      nonceArray[i] = newByte % 256
      if (newByte < 256) break
   }

   return nonceArray
}

export async function encrypt(attachment) {
   if (!attachment.fileObj.isEncrypted) {
      return attachment.rawBlob
   }
   let bytesToSkip = 0
   if (attachment.type === attachmentType.chunked) {
      bytesToSkip = chunkSize * attachment.fragmentSequence
   }
   let fileObj = attachment.fileObj
   let encrypMethod = fileObj.encryptionMethod
   if (encrypMethod === encryptionMethod.ChaCha20) {
      return await encryptWithChaCha20(fileObj.encryptionKey, fileObj.encryptionIv, attachment.rawBlob, bytesToSkip)

   } else if (encrypMethod === encryptionMethod.AesCtr) {
      return await encryptWithAesCtr(fileObj.encryptionKey, fileObj.encryptionIv, attachment.rawBlob, bytesToSkip)

   } else {
      console.warn("encrypt: invalid encryptionMethod: " + encrypMethod)
   }
   //encrypt a file
   //delete the old raw file to save up on RAM
}