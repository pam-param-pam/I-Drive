import i18n from "@/i18n/index.js"
import {useMainStore} from "@/stores/mainStore.js"
import {useToast} from "vue-toastification"

const toast = useToast()

export default function onEvent(message) {
   const store = useMainStore()


   let currentFolder = store.currentFolder
   let jsonObject = JSON.parse(message.data)

   if (jsonObject.op_code === 1) { // items created event
      for (let item of jsonObject.data) {
         if (item.parent_id !== currentFolder?.id) return
         store.updateItems(item)

      }

   }
   if (jsonObject.op_code === 2) { // items deleted event
      let updatedItems = store.items.filter(item => !jsonObject.data.includes(item.id))
      store.setItems(updatedItems)
      //if the deleted folder was the current folder, then let's redirect to root
      if (jsonObject.data.includes(currentFolder?.id)) {
         this.$router.push({name: `Files`})

      }

   }
   if (jsonObject.op_code === 3) { // item updated event
      let item = jsonObject.data
      if (item.parent_id !== currentFolder?.id) return
      store.updateItem(item)

   }

   if (jsonObject.op_code === 5) { // items moved event
      for (let item of jsonObject.data) {
         if (item.old_parent_id === currentFolder?.id) {
            //remove
            let updatedItems = store.items.filter(ListItem => ListItem.id !== item.item.id)
            store.setItems(updatedItems)
         }
         if (item.new_parent_id === currentFolder?.id) {
            //add
            store.updateItems(item.item)

         }
      }
   }
   if (jsonObject.op_code === 7) { // force folder navigation from server
      let folder_id = jsonObject.data.folder_id
      this.$router.push({name: `Files`, params: {"folderId": folder_id}})

   }

   if (jsonObject.op_code === 8) { // folder lock status change
      for (let item of jsonObject.data) {

         if (item.parent_id !== currentFolder?.id) return
         store.changeLockStatusAndPasswordCache({folderId: item.id, newLockStatus: item.isLocked, lockFrom: item.lockFrom})

      }

   }

   if (jsonObject.op_code === 9) { // items move to trash event
      // current view is 'Files'
      if (currentFolder) {
         for (let item of jsonObject.data) {

            let updatedItems = store.items.filter(ListItem => ListItem.id !== item.id)

            store.setItems(updatedItems)
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
            store.updateItems(item)

         }
      }

   }

   if (jsonObject.op_code === 10) { // items restore from trash event
      // current view is 'Files'
      if (currentFolder) {
         for (let item of jsonObject.data) {
            if (item.parent_id === currentFolder.id) {
               //add
               store.updateItems(item)
            }

         }
      }
      //current view is 'Trash'
      else {
         for (let item of jsonObject.data) {
            let updatedItems = store.items.filter(ListItem => ListItem.id !== item.id)
            store.setItems(updatedItems)

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
      console.warn("UPDATE")
      console.log(jsonObject)
      toast.update(jsonObject.task_id, {

         content: i18n.global.t(jsonObject.message, jsonObject.args),

         options: {timeout: timeout, type: type, draggable: true, closeOnClick: true}

      })
   }

}