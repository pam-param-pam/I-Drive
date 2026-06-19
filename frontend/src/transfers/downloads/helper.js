import { downloadFileStatus } from "@/transfers/downloads/constants.js"

export function isErrorStatus(status) {
   return status === downloadFileStatus.error
}