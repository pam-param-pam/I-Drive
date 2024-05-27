import Vue from "vue"
import buttons from "@/utils/buttons"
import {discord_instance} from "@/api/networker.js"

let MAX_CONCURRENT_REQUESTS = 4

const state = {
  id: 0,
  sizes: [],
  progress: [],
  queue: [],
  requestsUploading: 0,
  filesUploading: [],
  speedMbyte: 0,
  eta: 0,
}

const mutations = {
  setProgress(state, { id, loaded }) {
    Vue.set(state.progress, id, loaded)
  },
  reset: (state) => {
    state.id = 0
    state.sizes = []
    state.progress = []
  },
  addJob: (state, item) => {
    state.queue.push(item)
    //state.sizes[state.id] = item.file.size
    //state.id++
  },
  moveJob(state) {
    state.queue.shift()
  },

}

const beforeUnload = (event) => {
  event.preventDefault()
  event.returnValue = ""
}

const actions = {
  upload: (context, filesList) => {

    let isQueueEmpty = context.state.queue.length === 0
    let isUploadsEmpty = Object.keys(context.state.uploads).length === 0

    //if (isQueueEmpty && isUploadsEmpty) {
    //  window.addEventListener("beforeunload", beforeUnload)
    //}

    for (let file of filesList) {
      context.commit("addJob", file)
    }

  },
  finishUpload: (context, item) => {
    context.commit("setProgress", {id: item.id, loaded: item.file.size})
    context.dispatch("processUploads")
  },
  processUploads: async (context) => {
    let uploadsCount = Object.keys(context.state.uploads).length

    let isBellowLimit = context.state.requestsUploading < MAX_CONCURRENT_REQUESTS
    let isQueueEmpty = context.state.queue.length === 0
    let isUploadsEmpty = uploadsCount === 0

    let isFinished = isQueueEmpty && isUploadsEmpty
    let canProcess = isBellowLimit && !isQueueEmpty

    if (isFinished) {
      window.removeEventListener("beforeunload", beforeUnload)
      buttons.success("upload")
    }

    if (canProcess) {
      const item = context.state.queue[0]
      context.commit("moveJob")

      let url = context.rootState.settings.webhook
      discord_instance.post(url, {
        // Request data
      }, {
        onUploadProgress: function (progressEvent) {
          // Handle upload progress
          console.log(`Uploaded ${progressEvent.loaded} bytes out of ${progressEvent.total}`)
        }
      })
        .then(response => {
          // Handle response
        })
        .catch(error => {
          // Handle error
        })



    }

    context.dispatch("finishUpload", item)

  },
}

export default { state, mutations, actions, namespaced: true }
