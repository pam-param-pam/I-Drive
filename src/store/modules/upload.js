import buttons from "@/utils/buttons"
import {
  createNeededFolders,
  handleCreatingFiles,
  uploadCreatedFiles
} from "@/utils/upload.js"
import {discord_instance} from "@/api/networker.js";

let MAX_CONCURRENT_REQUESTS = 4
const chunkSize = 25 * 1023 * 1024 // <25MB in bytes

// Add all files in raw format to queue []
// Add local_id property to each
// first 5 files will be now displayed with property "creating..."
// create a better file structure + create folders + create files + get id and parent_id
// once it's all done
// start an uploading process, add them to filesUploading grab first 5 files, change their status to "uploading"
// continue till none left in queue.

const state = {
  queue: [],
  filesUploading: [],
  currentRequests: [],
  speedMbyte: 0,
  eta: 0,
  dummyLength: 0,

}

const mutations = {
  setStatus(state, { file_id, status}) {
    let file_obj = state.filesUploading.find(item => item.file_id === file_id)
    if (!file_obj) {
      console.warn(`No queueItem found for file_id: ${file_id}`)
      return
    }
    file_obj.status = status

  },
  setProgress(state, { file_id, chunkNumber, loadedBytes, totalBytes}) {
    let file_obj = state.filesUploading.find(item => item.file_id === file_id)
    if (!file_obj) {
      console.warn(`No queueItem found for file_id: ${file_id}`)
      return
    }

    totalBytes = file_obj.systemFile.size
    let allLoadedBytes = (chunkNumber -1) * 25 * 1024 * 1024 + loadedBytes
    let percentage = Math.round((allLoadedBytes / totalBytes) * 100)

    file_obj.status = "uploading"
    file_obj.progress = percentage
    console.log("loadedBytes")
    console.log(loadedBytes)
    console.log("totalBytes")
    console.log(totalBytes)

    console.log("percentage")
    console.log(percentage)
    if (percentage === 100) {

      file_obj.status = "success"
      setTimeout(() => {
        this.commit("upload/REMOVE_FILE_FROM_UPLOAD", file_id)

      }, 2500)
    }

  },
  REMOVE_FILE_FROM_UPLOAD(state, file_id) {
    state.filesUploading = state.filesUploading.filter(item => item.file_id !== file_id);
  },

  setMultiAttachmentProgress(state, { file_ids, progress}) {
    let percentage = Math.round(progress * 100)

    for (let file_id of file_ids) {
      let queueItem = state.filesUploading.find(item => item.file_id === file_id)

      if (!queueItem) {
        console.warn(`No queueItem found for file_id: ${file_id}`)
        return
      }
      queueItem.status = "uploading"
      queueItem.progress = percentage

      console.log("progress:")
      console.log(progress)

      console.log("percentage")
      console.log(percentage)

      if (percentage === 100) {
        queueItem.status  = "success"


        setTimeout(() => {
          this.commit("upload/REMOVE_FILE_FROM_UPLOAD", file_id)

        }, 2500)
      }
      // Optional: Log for debugging
      // console.log("file_id: " +  file_id);
      // console.log("percentage: " +  percentage);
      // console.log("totalBytes: " + totalBytes);


    }

  },

  moveJob(state) {

    let item = state.queue[0]
    state.queue.shift()
    state.filesUploading.push(item)
    console.log("state.filesUploading")
    console.log(state.filesUploading)
  },
  addToQueue: (state, item) => {
    console.log(item.file)
    let file = {
      name: item.name,
      file_id: item.file_id,
      systemFile: item.file,
      size: item.file.size,
      parent_id: item.parent_id,
      type: item.type,
      encryption_key: item.key,
      status: "waiting",
      progress: 1
    }

    state.queue.push(file)

  },
  cancelJob: (state, file_id) => {
    let index = state.queue.findIndex(item => item.file_id === file_id)
    if (index !== -1) {
      state.queue.splice(index, 1)
    }
  },
  pauseJob: (state, item) => {

  },
  replaceInQueue: (state, { queue_id, newItem }) => {
    let index = state.queue.findIndex(item => item.queue_id === queue_id)
    if (index !== -1) {
      newItem.queue_id = queue_id // Ensure the new item retains the same queue_id
      state.queue.splice(index, 1, newItem)
    }

  },
  setDummyLength: (state, length) => {
    state.dummyLength = length
  },


}

const beforeUnload = (event) => {
  event.preventDefault()
  event.returnValue = ""
}

const actions = {
  getFileFromQueue: (context) => {
    if (state.queue.length <= 0) return
    let fileObj = context.state.queue[0]
    context.commit("moveJob")
    return fileObj
  },
  upload: async (context, { filesList, parent_folder }) => {
    buttons.loading("upload")

    let isQueueEmpty = context.state.queue.length === 0
    //let isUploadsEmpty = Object.keys(context.state.uploads).length === 0
    let isUploadsEmpty = true
    if (isQueueEmpty && isUploadsEmpty) {
     window.addEventListener("beforeunload", beforeUnload)
    }
    console.log("filesList1:" + JSON.stringify(filesList))
    //context.state.dummyLength = filesList.length
    filesList = await createNeededFolders(filesList, parent_folder)
    console.log("filesList2:" + JSON.stringify(filesList))

    filesList.sort((a, b) => a.file.size - b.file.size)

    let createdFiles = await handleCreatingFiles(filesList)
    console.log("createdFiles1:" + JSON.stringify(createdFiles))

    for (let createdFile of createdFiles) {
      context.commit("addToQueue", createdFile)

    }


    await context.dispatch("processUploads")



  },

  processUploads: async (context) => {
    // let uploadsCount = Object.keys(context.state.filesUploading).length
    //
    // //let isBellowLimit = context.state.requestsUploading < MAX_CONCURRENT_REQUESTS
    // let isQueueEmpty = context.state.queue.length === 0
    // let isUploadsEmpty = uploadsCount === 0
    //
    // let isFinished = isQueueEmpty && isUploadsEmpty
    // let canProcess = isBellowLimit && !isQueueEmpty
    let isFinished = true
    let canProcess = true
    if (isFinished) {
      window.removeEventListener("beforeunload", beforeUnload)
      buttons.success("upload")
    }

    if (canProcess) {
      await uploadCreatedFiles()
    }

  },

}

export default { state, mutations, actions, namespaced: true }
