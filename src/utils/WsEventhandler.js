import vue from "@/utils/vue.js"
import store from "@/store"
import i18n from "@/i18n/index.js"

export default function onEvent(message) {
  let currentFolder = store.state.currentFolder
  let jsonObject = JSON.parse(message.data)
  if (jsonObject.op_code === 1) { // items created event
    for (let item of jsonObject.data) {
      if (item.parent_id !== currentFolder.id) return
      store.commit("updateItems", item)

    }

  }
  if (jsonObject.op_code === 2) { // items deleted event
    let updatedItems = store.state.items.filter(item => !jsonObject.data.includes(item.id))
    store.commit("setItems", updatedItems)
    //if the deleted folder was the current folder, then let's redirect to root
    if (jsonObject.data.includes(currentFolder.id)) {
      this.$router.push({name: `Files`})

    }

  }
  if (jsonObject.op_code === 3) { // items name change event
    for (let item of jsonObject.data) {
      if (item.parent_id !== currentFolder.id) return
      store.commit("renameItem", {id: item.id, newName: item.new_name})
    }
  }

  if (jsonObject.op_code === 5) { // items moved event
    for (let item of jsonObject.data) {
      if (item.old_parent_id === currentFolder.id) {
        //removeShare
        let updatedItems = store.state.items.filter(ListItem => ListItem.id !== item.item.id)
        store.commit("setItems", updatedItems)
      }
      if (item.new_parent_id === currentFolder.id) {
        //add
        store.commit("updateItems", item.item)

      }
    }
  }
  if (jsonObject.op_code === 6) { // items preview info add event
    for (let item of jsonObject.data) {
      if (item.parent_id !== currentFolder.id) return
      store.commit("updatePreviewInfo", {id: item.id, iso: item.iso,
        model_name: item.model_name, exposure_time: item.exposure_time,
        aperture: item.aperture, focal_length: item.focal_length})

    }
  }
  if (jsonObject.op_code === 7) { // force folder navigation from server
    let id = jsonObject.data.folder_id
    this.$router.push({name: `Files`, params: {"folderId": id}})

  }

  if (jsonObject.op_code === 8) { // folder lock status change
    console.log(1111)
    for (let item of jsonObject.data) {
      console.log(2222)

      if (item.parent_id !== currentFolder.id) return
      console.log(3333)

      store.commit("changeLockStatusAndPasswordCache", {folderId: item.id, newLockStatus: item.isLocked})
      console.log(4444)

    }

  }

  if (jsonObject.op_code === 9) { // items move to trash event
    // current view is 'Files'
    if (currentFolder) {
      console.log(JSON.stringify(jsonObject.data))
      for (let item of jsonObject.data) {

        let updatedItems = store.state.items.filter(ListItem => ListItem.id !== item.id)

        store.commit("setItems", updatedItems)

        //if the deleted folder was the current folder, then let's redirect to root
        if (jsonObject.data.includes(currentFolder.id)) {
          this.$router.push({name: `Files`})
        }
      }
    }
    //current view is 'Trash'
    else {
      for (let item of jsonObject.data) {
        //add
        store.commit("updateItems", item)
      }
    }

  }

  if (jsonObject.op_code === 10) { // items restore from trash event
    // current view is 'Files'
    if (currentFolder) {
      for (let item of jsonObject.data) {
        if (item.parent_id === currentFolder.id) {
          //add
          store.commit("updateItems", item)
        }

      }
    }
    //current view is 'Trash'
    else {
      for (let item of jsonObject.data) {
        let updatedItems = store.state.items.filter(ListItem => ListItem.id !== item.id)
        store.commit("setItems", updatedItems)
      }
    }

  }

  if (jsonObject.op_code === 4) { // message event, for example, when deleting items
    let timeout = 0
    let type = "info"
    //console.log(jsonObject.task_id)
    if (jsonObject.finished) {
      timeout = 3000

      type = "success"
    }
    if (jsonObject.error) {
      timeout = 0
      type = "error"
    }
    vue.$toast.update(jsonObject.task_id, {

      content: i18n.t(jsonObject.message),

      options: {timeout: timeout, type: type, draggable: true, closeOnClick: true}

    })
  }

}