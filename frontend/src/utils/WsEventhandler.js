import vue from "@/utils/vue.js";
import store from "@/store";
import router from "@/router/index.js";

export default function onEvent(message) {
  let currentFolder = store.state.currentFolder
  let jsonObject = JSON.parse(message.data);
  if (jsonObject.op_code === 1) { // items created event
    for (let item of jsonObject.data) {
      if (item.parent_id !== currentFolder.id) return
      store.commit("updateItems", item);

    }

  }
  if (jsonObject.op_code === 2) { // items deleted event
    let updatedItem = store.state.items.filter(item => !jsonObject.data.includes(item.id));
    store.commit("setItems", updatedItem);
    //if the deleted folder was the current folder, then let's redirect to root
    if (jsonObject.data.includes(currentFolder.id)) {
      router.push({path: `/files/`});

    }


  }
  if (jsonObject.op_code === 3) { // items name changed event
    for (let item of jsonObject.data) {
      if (item.parent_id !== currentFolder.id) return
      store.commit("renameItem", {id: item.id, newName: item.new_name});
      console.log("renamed")
    }
  }
  if (jsonObject.op_code === 5) { // items moved event
    for (let item of jsonObject.data) {
      if (item.old_parent_id === currentFolder.id) {
        //remove
        let updatedItem = store.state.items.filter(ListItem => ListItem.id !== item.item.id);
        store.commit("setItems", updatedItem);
      }
      if (item.new_parent_id === currentFolder.id) {
        //add
        store.commit("updateItems", item.item);

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

      content: jsonObject.message,
      options: {timeout: timeout, type: type, draggable: true, closeOnClick: true}

    });
  }

}