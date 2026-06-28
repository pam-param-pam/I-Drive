import { FileConsumer } from "@/transfers/downloads/workers/fileConsumer.js"
import { downloadState } from "@/transfers/downloads/constants.js"
import { encryptionMethod } from "@/utils/constants.js"
import { ZipTransformParser } from "@/transfers/downloads/utils/ZipParser.js"
import { decryptAesCtr, decryptChaCha20CryptographyCompatible } from "@/utils/crypto/decryption.js"
import { bytesToBase64 } from "@/utils/crypto/encryption.js"
import { HttpDownloadError } from "@/transfers/downloads/utils/helper.js"


export class ZipConsumer extends FileConsumer {
   constructor({ zipQueue, downloadRuntime }) {
      super({
         fileQueue: zipQueue,
         downloadRuntime
      })

      this.zipQueue = zipQueue
   }

   async fetchFile(queueItem, signal) {
      const options = {
         signal,
         headers: {}
      }

      if (queueItem.offset > 0) {
         options.headers.Range = `bytes=${queueItem.offset}-`
      }

      return await fetch(queueItem.file.downloadUrl, options)
   }

   async validateResponse(response, queueItem) {
      if (!response.ok) {
         throw new HttpDownloadError(response.status, response.statusText)
      }

      if (queueItem.offset > 0 && response.status !== 206) {
         throw new Error("ZIP download cannot be resumed: server ignored Range request")
      }

      const expectedSize = queueItem.file.size - queueItem.offset
      const contentLength = response.headers.get("content-length")

      if (Number(contentLength) !== expectedSize) {
         throw new Error(`ZIP size mismatch. Expected ${expectedSize}, got ${contentLength}`)
      }
   }

   async saveResponseToDisk(response, queueItem, signal) {
      const { file } = queueItem
      const totalBytes = file.size

      const reader = response.body.getReader()
      const writable = await queueItem.fileHandle.createWritable({
         keepExistingData: queueItem.offset > 0
      })

      const parser = new ZipTransformParser({
         resumeState: queueItem.zipParserState
      })

      try {
         if (queueItem.offset > 0) {
            await writable.seek(queueItem.offset)
         }

         while (true) {
            if (signal.aborted) {
               throw new DOMException("Aborted", "AbortError")
            }

            if (this.downloadRuntime.downloadState !== downloadState.downloading) {
               await this.downloadRuntime.waitUntilResumed(signal)
               continue
            }

            const { value, done } = await reader.read()

            if (signal.aborted) {
               throw new DOMException("Aborted", "AbortError")
            }

            if (done) {
               break
            }

            const outputChunks = await this.transformZipChunk(parser, value, signal)

            let writtenInBatch = 0

            for (const outputChunk of outputChunks) {
               if (signal.aborted) {
                  throw new DOMException("Aborted", "AbortError")
               }

               if (this.downloadRuntime.downloadState !== downloadState.downloading) {
                  await this.downloadRuntime.waitUntilResumed(signal)
               }

               await writable.write(outputChunk)

               writtenInBatch += outputChunk.byteLength

               this.emitProgress(
                  file,
                  queueItem.offset + writtenInBatch,
                  totalBytes
               )
            }

            queueItem.offset += writtenInBatch
            queueItem.zipParserState = parser.getResumeState()
         }

         const finalChunks = await this.flushZipParser(parser, signal)

         let writtenInFlush = 0

         for (const outputChunk of finalChunks) {
            if (signal.aborted) {
               throw new DOMException("Aborted", "AbortError")
            }

            await writable.write(outputChunk)

            writtenInFlush += outputChunk.byteLength

            this.emitProgress(
               file,
               queueItem.offset + writtenInFlush,
               totalBytes
            )
         }

         queueItem.offset += writtenInFlush
         queueItem.zipParserState = parser.getResumeState()

         this.emitProgress.flush()
      } finally {
         this.emitProgress.cancel()
         reader.releaseLock()
         await writable.close()
      }
   }

   async transformZipChunk(parser, inputChunk, signal) {
      const parts = parser.push(inputChunk)
      const outputChunks = []

      const outputLengthCheck = parts.reduce((sum, part) => sum + part.bytes.byteLength, 0)

      if (outputLengthCheck !== inputChunk.byteLength) {
         throw new Error( `ZIP parser length mismatch: input ${inputChunk.byteLength}, parts ${outputLengthCheck}`)
      }

      for (const part of parts) {
         if (signal.aborted) {
            throw new DOMException("Aborted", "AbortError")
         }

         outputChunks.push(await this.transformZipPart(part))
      }

      return outputChunks
   }

   async flushZipParser(parser, signal) {
      const parts = parser.flush()
      const outputChunks = []

      for (const part of parts) {
         if (signal.aborted) {
            throw new DOMException("Aborted", "AbortError")
         }

         outputChunks.push(await this.transformZipPart(part))
      }

      return outputChunks
   }

   async transformZipPart(part) {
      if (part.type === "localHeader") {
         return this.maskLocalHeaderEncryptionExtra(part)
      }

      if (part.type !== "fileData") {
         return part.bytes
      }

      const cryptoParams = part.encryption

      if (!this.isEncrypted(cryptoParams)) {
         return part.bytes
      }

      const startByte = this.getEntryRelativeOffset(part)

      const decryptedBytes = await this.decryptZipData(
         part.bytes,
         cryptoParams,
         startByte
      )

      if (decryptedBytes.byteLength !== part.bytes.byteLength) {
         throw new Error(
            `ZIP decrypt length mismatch for ${part.filename ?? "entry"}: ` +
            `expected ${part.bytes.byteLength}, got ${decryptedBytes.byteLength}`
         )
      }

      return decryptedBytes
   }

   maskLocalHeaderEncryptionExtra(part) {
      if (
         part.encryptionExtraPayloadStart === null ||
         part.encryptionExtraPayloadEnd === null
      ) {
         return part.bytes
      }

      const start = part.encryptionExtraPayloadStart
      const end = part.encryptionExtraPayloadEnd
      const length = end - start

      const bytes = new Uint8Array(part.bytes)
      const randomBytes = new Uint8Array(length)

      crypto.getRandomValues(randomBytes)
      bytes.set(randomBytes, start)

      return bytes
   }

   getEntryRelativeOffset(part) {
      return Number(part.fileOffset)
   }

   isEncrypted(cryptoParams) {
      return cryptoParams?.extraFieldFound &&
         cryptoParams.method !== encryptionMethod.NotEncrypted
   }

   async decryptZipData(bytes, cryptoParams, startByte) {
      const keyBase64 = bytesToBase64(cryptoParams.key)
      const ivBase64 = bytesToBase64(cryptoParams.iv)

      if (cryptoParams.method === encryptionMethod.AesCtr) {
         return await decryptAesCtr(bytes, keyBase64, ivBase64, startByte)
      }

      if (cryptoParams.method === encryptionMethod.ChaCha20) {
         return decryptChaCha20CryptographyCompatible(
            bytes,
            keyBase64,
            ivBase64,
            startByte
         )
      }

      throw new Error(`Unsupported ZIP encryption method: ${cryptoParams.method}`)
   }
}