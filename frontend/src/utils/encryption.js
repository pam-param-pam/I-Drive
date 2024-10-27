import JSChaCha20 from "js-chacha20"

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

export async function encrypt(attachment) {
   //encrypt a file
   //delete the old raw file to save up on RAM
}