export const uploadType = {
   browserInput: "browserInput",
   dragAndDropInput: "dragAndDropInput"
}

export const attachmentType = {
   file: "file",
   thumbnail: "thumbnail",
   subtitle: "subtitle"
}
export const uploadFileStatus = {
   preparing: "preparing",
   uploading: "uploading",
   uploaded: "uploaded",
   waitingForSave: "waitingForSave",
   uploadFailed: "uploadFailed",
   saveFailed: "saveFailed",
   errorOccurred: "errorOccurred",
   waitingForInternet: "waitingForInternet",
   retrying: "retrying",
   fileGoneInUpload: "fileGoneInUpload",
   fileGoneInRequestProducer: "fileGoneInRequestProducer"
}

export const uploadState = {
   idle: "idle",
   uploading: "uploading",
   paused: "paused",
   noInternet: "noInternet",
   error: "error",
   aborting: "aborting"
}