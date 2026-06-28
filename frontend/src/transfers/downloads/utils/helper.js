import { downloadFileStatus } from "@/transfers/downloads/constants.js"

export function isErrorStatus(status) {
   return status === downloadFileStatus.failed || status === downloadFileStatus.errorOccurred
}

export class HttpDownloadError extends Error {
   constructor(status, statusText) {
      super(`Download failed: HTTP ${status}`)
      this.name = "HttpDownloadError"
      this.status = status
      this.statusText = statusText
   }
}

export class FilePickerNotSupported extends Error {
   constructor() {
      super(`Your bowser doesn't support client side decryption.`)
   }
}