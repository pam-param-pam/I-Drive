import { encryptionMethod } from "@/utils/constants.js"

const LOCAL_FILE_HEADER_SIG = 0x04034b50
const CENTRAL_DIR_SIG = 0x02014b50
const EOCD_SIG = 0x06054b50
const ZIP64_EOCD_SIG = 0x06064b50
const ZIP64_EOCD_LOCATOR_SIG = 0x07064b50
const CENTRAL_DIR_DIGITAL_SIGNATURE_SIG = 0x05054b50
const ARCHIVE_EXTRA_DATA_SIG = 0x08064b50
const DATA_DESCRIPTOR_SIG = 0x08074b50

const DATA_DESCRIPTOR_FLAG = 0x0008
const ZIP64_EXTRA_ID = 0x0001
const ENCRYPTION_EXTRA_ID = 0xcafe

const AES_CTR_IV_LENGTH = 16
const CHACHA20_IV_LENGTH = 12


function concatBytes(a, b) {
   const out = new Uint8Array(a.byteLength + b.byteLength)
   out.set(a, 0)
   out.set(b, a.byteLength)
   return out
}


function u16(data, offset) {
   return data[offset] | (data[offset + 1] << 8)
}


function u32(data, offset) {
   return (
      data[offset] |
      (data[offset + 1] << 8) |
      (data[offset + 2] << 16) |
      (data[offset + 3] << 24)
   ) >>> 0
}


function u64(data, offset) {
   const lo = BigInt(u32(data, offset))
   const hi = BigInt(u32(data, offset + 4))
   return (hi << 32n) | lo
}


function isZipMetadataSig(sig) {
   return sig === CENTRAL_DIR_SIG ||
      sig === EOCD_SIG ||
      sig === ZIP64_EOCD_SIG ||
      sig === ZIP64_EOCD_LOCATOR_SIG ||
      sig === CENTRAL_DIR_DIGITAL_SIGNATURE_SIG ||
      sig === ARCHIVE_EXTRA_DATA_SIG
}


function isZipHeaderSig(sig) {
   return sig === LOCAL_FILE_HEADER_SIG || isZipMetadataSig(sig)
}


function defaultEncryptionInfo() {
   return {
      extraFieldFound: false,
      method: encryptionMethod.NotEncrypted,
      iv: null,
      key: null
   }
}


function parseZip64CompressedSize(extra, compressedSize32, uncompressedSize32) {
   if (compressedSize32 !== 0xffffffff) {
      return BigInt(compressedSize32)
   }

   let offset = 0

   while (offset + 4 <= extra.byteLength) {
      const headerId = u16(extra, offset)
      const dataSize = u16(extra, offset + 2)

      const dataStart = offset + 4
      const dataEnd = dataStart + dataSize

      if (headerId === ZIP64_EXTRA_ID) {
         let p = dataStart

         if (uncompressedSize32 === 0xffffffff) {
            p += 8
         }

         return u64(extra, p)
      }

      offset = dataEnd
   }

   throw new Error("ZIP64 compressed size not found")
}


function parseEncryptedPayload({ extra, dataStart, dataEnd, method, ivLength }) {
   const payloadStart = dataStart + 2

   return {
      extraFieldFound: true,
      method,
      iv: extra.slice(payloadStart, payloadStart + ivLength),
      key: extra.slice(payloadStart + ivLength, dataEnd)
   }
}


function parseEncryptionExtra(extra) {
   let offset = 0

   while (offset + 4 <= extra.byteLength) {
      const headerId = u16(extra, offset)
      const dataSize = u16(extra, offset + 2)

      const dataStart = offset + 4
      const dataEnd = dataStart + dataSize

      if (headerId === ENCRYPTION_EXTRA_ID) {
         const method = u16(extra, dataStart)

         const range = {
            found: true,
            payloadStartInExtra: dataStart,
            payloadEndInExtra: dataEnd
         }

         if (method === encryptionMethod.NotEncrypted) {
            return {
               encryption: {
                  extraFieldFound: true,
                  method,
                  iv: null,
                  key: null
               },
               range
            }
         }

         if (method === encryptionMethod.AesCtr) {
            return {
               encryption: parseEncryptedPayload({
                  extra,
                  dataStart,
                  dataEnd,
                  method,
                  ivLength: AES_CTR_IV_LENGTH
               }),
               range
            }
         }

         if (method === encryptionMethod.ChaCha20) {
            return {
               encryption: parseEncryptedPayload({
                  extra,
                  dataStart,
                  dataEnd,
                  method,
                  ivLength: CHACHA20_IV_LENGTH
               }),
               range
            }
         }

         throw new Error(`Unknown encryption method in ZIP extra field: ${method}`)
      }

      offset = dataEnd
   }

   return {
      encryption: defaultEncryptionInfo(),
      range: {
         found: false,
         payloadStartInExtra: null,
         payloadEndInExtra: null
      }
   }
}


export class ZipTransformParser {
   constructor({ resumeState } = {}) {
      this.buffer = new Uint8Array(0)

      this.state = resumeState?.state ?? "localHeader"
      this.currentEntry = resumeState?.currentEntry ?? null
      this.remainingFileData = resumeState?.remainingFileData ?? 0n
      this.currentFileOffset = resumeState?.currentFileOffset ?? 0n

      this.done = resumeState?.done ?? false
   }

   getResumeState() {
      return {
         state: this.state,
         currentEntry: this.currentEntry,
         remainingFileData: this.remainingFileData,
         currentFileOffset: this.currentFileOffset,
         done: this.done
      }
   }

   push(chunk) {
      const parts = []

      if (this.done) {
         parts.push({
            type: "passthrough",
            bytes: chunk
         })

         return parts
      }

      if (chunk.byteLength > 0) {
         this.buffer = concatBytes(this.buffer, chunk)
      }

      while (!this.done) {
         if (this.state === "localHeader") {
            if (!this.parseLocalHeader(parts)) break
            continue
         }

         if (this.state === "fileData") {
            if (!this.emitFileData(parts)) break
            continue
         }

         if (this.state === "dataDescriptor") {
            if (!this.emitDataDescriptor(parts)) break
            continue
         }

         throw new Error(`Unknown ZIP parser state: ${this.state}`)
      }

      return parts
   }

   flush() {
      if (this.buffer.byteLength === 0) return []

      const bytes = this.buffer
      this.buffer = new Uint8Array(0)

      return [{ type: "passthrough", bytes }]
   }

   parseLocalHeader(parts) {
      if (this.buffer.byteLength < 4) return false

      const sig = u32(this.buffer, 0)

      if (isZipMetadataSig(sig)) {
         this.done = true

         parts.push({
            type: "passthrough",
            bytes: this.buffer
         })

         this.buffer = new Uint8Array(0)
         return false
      }

      if (sig !== LOCAL_FILE_HEADER_SIG) {
         throw new Error(`Expected local file header, got 0x${sig.toString(16)}`)
      }

      if (this.buffer.byteLength < 30) return false

      const flags = u16(this.buffer, 6)

      const compressedSize32 = u32(this.buffer, 18)
      const uncompressedSize32 = u32(this.buffer, 22)

      const filenameLength = u16(this.buffer, 26)
      const extraLength = u16(this.buffer, 28)

      const localHeaderLength = 30 + filenameLength + extraLength

      if (this.buffer.byteLength < localHeaderLength) return false

      const filenameBytes = this.buffer.slice(30, 30 + filenameLength)
      const filename = new TextDecoder("utf-8").decode(filenameBytes)

      const extraStart = 30 + filenameLength
      const extraEnd = extraStart + extraLength
      const extra = this.buffer.slice(extraStart, extraEnd)

      const compressedSize = parseZip64CompressedSize(extra, compressedSize32, uncompressedSize32)
      const { encryption, range } = parseEncryptionExtra(extra)

      const localHeader = this.buffer.slice(0, localHeaderLength)

      this.buffer = this.buffer.slice(localHeaderLength)

      this.currentEntry = {
         filename,
         compressedSize,
         encryption,
         isDirectory: filename.endsWith("/"),
         hasDataDescriptor: (flags & DATA_DESCRIPTOR_FLAG) !== 0,
         zip64: compressedSize32 === 0xffffffff || uncompressedSize32 === 0xffffffff
      }

      this.remainingFileData = compressedSize
      this.currentFileOffset = 0n
      this.state = "fileData"

      parts.push({
         type: "localHeader",
         filename,
         bytes: localHeader,
         encryption,
         encryptionExtraPayloadStart: range.found ? extraStart + range.payloadStartInExtra : null,
         encryptionExtraPayloadEnd: range.found ? extraStart + range.payloadEndInExtra : null
      })

      return true
   }

   emitFileData(parts) {
      if (this.remainingFileData === 0n) {
         if (this.currentEntry.hasDataDescriptor && !this.currentEntry.isDirectory) {
            this.state = "dataDescriptor"
         } else {
            this.currentEntry = null
            this.currentFileOffset = 0n
            this.state = "localHeader"
         }

         return true
      }

      if (this.buffer.byteLength === 0) {
         return false
      }

      const n = Number(
         this.remainingFileData < BigInt(this.buffer.byteLength)
            ? this.remainingFileData
            : BigInt(this.buffer.byteLength)
      )

      const bytes = this.buffer.slice(0, n)

      parts.push({
         type: "fileData",
         filename: this.currentEntry.filename,
         bytes,
         fileOffset: Number(this.currentFileOffset),
         encryption: this.currentEntry.encryption
      })

      this.buffer = this.buffer.slice(n)
      this.remainingFileData -= BigInt(n)
      this.currentFileOffset += BigInt(n)

      return true
   }

   emitDataDescriptor(parts) {
      if (this.buffer.byteLength < 4) {
         return false
      }

      const sig = u32(this.buffer, 0)

      if (isZipHeaderSig(sig)) {
         this.currentEntry = null
         this.currentFileOffset = 0n
         this.state = "localHeader"
         return true
      }

      const hasSignature = sig === DATA_DESCRIPTOR_SIG
      const descriptorLength = this.currentEntry.zip64 ? (hasSignature ? 24 : 20) : (hasSignature ? 16 : 12)

      if (this.buffer.byteLength < descriptorLength) {
         return false
      }

      const bytes = this.buffer.slice(0, descriptorLength)

      parts.push({
         type: "passthrough",
         bytes
      })

      this.buffer = this.buffer.slice(descriptorLength)

      this.currentEntry = null
      this.currentFileOffset = 0n
      this.state = "localHeader"

      return true
   }
}