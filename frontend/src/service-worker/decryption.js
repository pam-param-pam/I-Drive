function base64ToBytes(value) {
   const binary = atob(value)
   const bytes = new Uint8Array(binary.length)

   for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
   }

   return bytes
}

export async function decryptAesCtr(encryptedBytes, keyBase64, ivBase64, startByte) {
   const keyBytes = base64ToBytes(keyBase64)
   const ivBytes = base64ToBytes(ivBase64)

   if (keyBytes.byteLength !== 32) {
      throw new Error(`AES key must be 32 bytes, got ${keyBytes.byteLength}`)
   }

   if (ivBytes.byteLength !== 16) {
      throw new Error(`AES CTR IV must be 16 bytes, got ${ivBytes.byteLength}`)
   }

   const blockSize = 16
   const blocksToSkip = Math.floor(startByte / blockSize)
   const counterOffset = startByte % blockSize
   const counter = incrementBigEndianCounter(ivBytes, blocksToSkip)

   const cryptoKey = await crypto.subtle.importKey("raw", keyBytes, { name: "AES-CTR" }, false, ["decrypt"])

   let input

   if (counterOffset === 0) {
      input = encryptedBytes
   } else {
      input = new Uint8Array(counterOffset + encryptedBytes.byteLength)
      input.set(encryptedBytes, counterOffset)
   }

   const decryptedBuffer = await crypto.subtle.decrypt({
      name: "AES-CTR",
      counter,
      length: 128
   }, cryptoKey, input)

   const decryptedBytes = new Uint8Array(decryptedBuffer)

   if (counterOffset === 0) {
      return decryptedBytes
   }

   return decryptedBytes.slice(counterOffset)
}


function incrementBigEndianCounter(ivBytes, blocksToSkip) {
   const result = new Uint8Array(ivBytes)
   let carry = BigInt(blocksToSkip)

   for (let i = result.length - 1; i >= 0 && carry > 0n; i--) {
      const sum = BigInt(result[i]) + (carry & 0xffn)
      result[i] = Number(sum & 0xffn)
      carry = (carry >> 8n) + (sum >> 8n)
   }

   if (carry > 0n) {
      throw new Error("AES CTR counter overflow")
   }

   return result
}


export function decryptChaCha20CryptographyCompatible(encryptedBytes, keyBase64, ivBase64, startByte) {
   const keyBytes = base64ToBytes(keyBase64)
   const ivBytes = base64ToBytes(ivBase64)

   if (keyBytes.byteLength !== 32) {
      throw new Error(`ChaCha20 key must be 32 bytes, got ${keyBytes.byteLength}`)
   }

   if (ivBytes.byteLength !== 12) {
      throw new Error(`ChaCha20 stored IV must be 12 bytes, got ${ivBytes.byteLength}`)
   }

   const blockSize = 64
   const blocksToSkip = Math.floor(startByte / blockSize)
   const counterOffset = startByte % blockSize

   return chacha20XorCryptographyCompatible(encryptedBytes, keyBytes, ivBytes, blocksToSkip, counterOffset)
}


function chacha20XorCryptographyCompatible(input, key, iv12, initialBlockCounter, counterOffset) {
   const output = new Uint8Array(input.byteLength)

   let inputPos = 0
   let blockCounterLow = initialBlockCounter >>> 0

   const counterHighFromIv = load32LE(iv12, 0)
   const nonceWord0 = load32LE(iv12, 4)
   const nonceWord1 = load32LE(iv12, 8)

   while (inputPos < input.byteLength) {
      const keyStream = chacha20Block(key, blockCounterLow, counterHighFromIv, nonceWord0, nonceWord1)
      const start = inputPos === 0 ? counterOffset : 0

      for (let i = start; i < 64 && inputPos < input.byteLength; i++) {
         output[inputPos] = input[inputPos] ^ keyStream[i]
         inputPos++
      }

      blockCounterLow = (blockCounterLow + 1) >>> 0
   }

   return output
}


function chacha20Block(key, counterLow, counterHigh, nonce0, nonce1) {
   const state = new Uint32Array(16)

   state[0] = 0x61707865
   state[1] = 0x3320646e
   state[2] = 0x79622d32
   state[3] = 0x6b206574

   state[4] = load32LE(key, 0)
   state[5] = load32LE(key, 4)
   state[6] = load32LE(key, 8)
   state[7] = load32LE(key, 12)
   state[8] = load32LE(key, 16)
   state[9] = load32LE(key, 20)
   state[10] = load32LE(key, 24)
   state[11] = load32LE(key, 28)

   state[12] = counterLow
   state[13] = counterHigh
   state[14] = nonce0
   state[15] = nonce1

   const working = new Uint32Array(state)

   for (let i = 0; i < 10; i++) {
      quarterRound(working, 0, 4, 8, 12)
      quarterRound(working, 1, 5, 9, 13)
      quarterRound(working, 2, 6, 10, 14)
      quarterRound(working, 3, 7, 11, 15)

      quarterRound(working, 0, 5, 10, 15)
      quarterRound(working, 1, 6, 11, 12)
      quarterRound(working, 2, 7, 8, 13)
      quarterRound(working, 3, 4, 9, 14)
   }

   for (let i = 0; i < 16; i++) {
      working[i] = (working[i] + state[i]) >>> 0
   }

   const out = new Uint8Array(64)

   for (let i = 0; i < 16; i++) {
      store32LE(out, i * 4, working[i])
   }

   return out
}


function quarterRound(x, a, b, c, d) {
   x[a] = (x[a] + x[b]) >>> 0
   x[d] = rotateLeft32(x[d] ^ x[a], 16)

   x[c] = (x[c] + x[d]) >>> 0
   x[b] = rotateLeft32(x[b] ^ x[c], 12)

   x[a] = (x[a] + x[b]) >>> 0
   x[d] = rotateLeft32(x[d] ^ x[a], 8)

   x[c] = (x[c] + x[d]) >>> 0
   x[b] = rotateLeft32(x[b] ^ x[c], 7)
}


function rotateLeft32(value, shift) {
   return ((value << shift) | (value >>> (32 - shift))) >>> 0
}


function load32LE(bytes, offset) {
   return (
      bytes[offset] |
      (bytes[offset + 1] << 8) |
      (bytes[offset + 2] << 16) |
      (bytes[offset + 3] << 24)
   ) >>> 0
}

function store32LE(bytes, offset, value) {
   bytes[offset] = value & 0xff
   bytes[offset + 1] = (value >>> 8) & 0xff
   bytes[offset + 2] = (value >>> 16) & 0xff
   bytes[offset + 3] = (value >>> 24) & 0xff
}