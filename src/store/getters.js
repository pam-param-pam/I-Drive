const getters = {
  isLogged: (state) => {
    return state.user !== null
  },
  getFolderPassword: (state) => (folderId) => {
    return state.folderPasswords[folderId] || null
  },
  isFiles: (state) => !state.loading && state.route.name === "Files",
  isListing: (state, getters) => getters.isFiles && state.req.isDir,
  selectedCount: (state) => state.selected.length,
  progress: (state) => {
    // if (state.upload.progress.length === 0) {
    //   return 0
    // }
    //
    // let totalSize = state.upload.sizes.reduce((a, b) => a + b, 0)
    //
    // let sum = state.upload.progress.reduce((acc, val) => acc + val)
    // return Math.ceil((sum / totalSize) * 100)
    // return 20
  },
  filesInUploadCount: (state) => {

    return state.upload.queue.length + state.upload.filesUploading.length
  },
  filesInUpload: (state) => {
    let files = []
    for (let file of state.upload.filesUploading.values()) {

      let id = file.file_id
      let name = file.name
      let parent_id = file.parent_id
      let size = file.systemFile.size
      let progress =  file.progress
      let type = file.type
      let status = file.status
      files.push({
        status,
        type,
        size,
        id,
        parent_id,
        name,
        progress,
      })

    }

    // return files.sort((a, b) => a.progress - b.progress).slice(0, 10)
    return files.sort((a, b) => a.progress - b.progress)

  },
  previousPrompt: (state) => {
    return state.prompts.length > 1
      ? state.prompts[state.prompts.length - 2]
      : null
  },
  currentPrompt: (state) => {
    return state.prompts.length > 0
      ? state.prompts[state.prompts.length - 1]
      : null
  },
  currentPromptName: (_, getters) => {
    return getters.currentPrompt?.prompt
  },
  previousPromptName: (_, getters) => {
    return getters.previousPrompt?.prompt
  },
  uploadSpeed: (state) => state.upload.speedMbyte,
  eta: (state) => state.upload.eta,
}

export default getters
