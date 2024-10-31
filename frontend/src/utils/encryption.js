import JSChaCha20 from "js-chacha20"
import { attachmentType, chunkSize, encryptionMethod } from "@/utils/constants.js"

function base64ToUint8Array(base64) {
   let binaryString = window.atob(base64)
   let len = binaryString.length
   let bytes = new Uint8Array(len)
   for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i)
   }
   return bytes
}

export async function encryptWithAesCtr(base64Key, base64IV, file, bytesToSkip) {

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
      { name: "AES-CTR", counter: iv, length: 64 },
      cryptoKey,
      arrayBuffer
   )

   return new Blob([new Uint8Array(encryptedArrayBuffer)], { type: file.type })
}

export async function encryptWithChaCha20(base64Key, base64IV, file, bytesToSkip) {

   let key = base64ToUint8Array(base64Key)
   let iv = base64ToUint8Array(base64IV)

   let counter = calculateCounter(bytesToSkip)
   let arrayBuffer = await file.arrayBuffer()
   console.log("counter")
   console.log(counter)

   let encryptedData = new JSChaCha20(key, iv, counter).encrypt(new Uint8Array(arrayBuffer))


   return new Blob([new Uint8Array(encryptedData)], { type: file.type })
}
// Convert the byte array to an integer (big-endian)
function bytesToInt(byteArray) {
   let value = 0; // Regular number
   for (let i = 0; i < byteArray.length; i++) {
      value = (value << 8) | byteArray[i];
      if (value < 0) {
         // Handle overflow if needed
         console.warn('Value has exceeded safe integer limit.');
      }
   }
   return value
}
function intToBytes(length, int) {
   const byteArray = new Uint8Array(length);
   for (let i = length - 1; i >= 0; i--) {
      byteArray[i] = int & 0xff; // Get the last 8 bits of the integer
      int = int >> 8; // Shift the integer 8 bits to the right
   }
   return byteArray;
}
// Function to add two Uint16Arrays with a fixed length of 16
function addUint16ArraysFixedLength(arr1, arr2) {
   // Create a new Uint16Array to hold the result with a fixed length of 16
   const result = new Uint16Array(16);

   // Loop through each index in the result array
   for (let i = 0; i < result.length; i++) {
      const val1 = arr1[i % arr1.length] || 0; // Wrap around arr1
      const val2 = arr2[i % arr2.length] || 0; // Wrap around arr2
      result[i] = val1 + val2;

      // Optionally, cap the value at maximum Uint16
      if (result[i] > 0xFFFF) {
         result[i] = 0xFFFF; // Cap at maximum Uint16 value
      }
   }

   return result;
}

// AES Counter (CTR) Helper for IV Increment
function incrementIV(iv, bytesToSkip) {

   console.log("iv")
   console.log(iv)
   let blocksToSkip = Math.floor(bytesToSkip / 16)
   console.log("blocksToSkip")
   console.log(blocksToSkip)


   let adjustedCounter = intToBytes(iv.length, blocksToSkip); // Convert to 16-byte big-endian array
   console.log("adjustedCounter")
   console.log(adjustedCounter)


   let newIv = addUint16ArraysFixedLength(iv, adjustedCounter);

   console.log("newIv")
   console.log(newIv)



   return newIv

}

function calculateCounter(bytesToSkip) {
   if (bytesToSkip === 0) {
      return 0
   }

   let blocksToSkip = Math.floor(bytesToSkip / 64) // ChaCha20 block size is 64 bytes
   return blocksToSkip

}

export async function encrypt(attachment) {
   if (!attachment.fileObj.isEncrypted) {
      return attachment.rawBlob
   }
   let bytesToSkip = 0

   if (attachment.type === attachmentType.chunked) {
      bytesToSkip = chunkSize * (attachment.fragmentSequence-1)
   }
   console.log("bytesToSkip11111111111111")
   console.log(bytesToSkip)

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