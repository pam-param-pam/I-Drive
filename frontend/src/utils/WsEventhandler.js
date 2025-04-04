import i18n from "@/i18n/index.js"
import { useMainStore } from "@/stores/mainStore.js"
import { useToast } from "vue-toastification"
import { logout } from "@/utils/auth.js"
import router from "@/router/index.js"

const toast = useToast()


async function deriveKey(variableKey) {
   const encoder = new TextEncoder()
   const keyData = encoder.encode(variableKey)

   const hash = await crypto.subtle.digest("SHA-256", keyData)
   return hash
}


async function decryptMessage(key, encryptedData) {
   const keyBytes = await deriveKey(key)
   const encryptedBuffer = Uint8Array.from(atob(encryptedData), c => c.charCodeAt(0))

   const iv = encryptedBuffer.slice(0, 16) // First 16 bytes (IV)
   const ciphertext = encryptedBuffer.slice(16) // Remaining encrypted data

   const cryptoKey = await crypto.subtle.importKey(
      "raw", keyBytes, { name: "AES-CBC", length: 256 }, false, ["decrypt"]
   )


   const decryptedBuffer = await crypto.subtle.decrypt(
      { name: "AES-CBC", iv },
      cryptoKey,
      ciphertext
   )

   const decodedText = new TextDecoder().decode(decryptedBuffer)
   return JSON.parse(decodedText) // Try parsing JSON, else return string

}


export async function onEvent(message) {
   const store = useMainStore()
   /**
    Each event looks like this:
    {"is_encrypted": bool, "lockFrom": int/null, event: {"op_code": int, "folder_context_id", str, "data": [...], ...other data specific for op_code}}
    */
   let currentFolder = store.currentFolder
   let jsonObject = JSON.parse(message.data)
   let event = jsonObject.event
   let folder_context_id = jsonObject.folder_context_id
   let currentRoute = router.currentRoute.value.name

   if (jsonObject.is_encrypted) {
      let password = store.getFolderPassword(jsonObject.lockFrom)
      event = await decryptMessage(password, event)
   }

   let op_code = event?.op_code

   console.log(jsonObject)
   console.log(event)
   console.log(currentRoute)

   if (op_code === 1) { // items created event
      if (folder_context_id !== currentFolder?.id) return
      for (let item of event.data) {
         store.pushToItems(item)
      }

   }
   if (op_code === 2) { // items deleted event
      if (currentRoute === "Trash") {
         let updatedItems = store.items.filter(item => !event.data.includes(item.id))
         store.setItems(updatedItems)
      }
      //if the deleted folder was the current folder, then let's redirect to root
      if (event.data.includes(currentFolder?.id)) {
         this.$router.push({ name: `Files` })

      }

   }
   if (op_code === 3) { // items updated event
      for (let item of event.data) {
         if (item.parent_id !== currentFolder?.id) continue
         store.updateItem(item)
      }
   }

   if (op_code === 4) { // items move-out event
      if (folder_context_id !== currentFolder?.id) return
      let updatedItems = store.items.filter(item => !event.data.includes(item.id))
      store.setItems(updatedItems)
   }

   if (op_code === 5) { // items move-in event
      for (let item of event.data) {
         if (item.parent_id !== currentFolder?.id) continue
         store.pushToItems(item)
      }
   }

   if (op_code === 6) { // items move to trash event
      for (let item of event.data) {
         if (currentRoute === "Trash") {
            store.pushToItems(item)
         } else if (item.parent_id === currentFolder?.id) {
            let updatedItems = store.items.filter(item1 => item1.id !== item.id)
            store.setItems(updatedItems)
         }
      }
   }

   if (op_code === 7) { // items restore from trash event
      for (let item of event.data) {
         if (currentRoute === "Trash") {
            let updatedItems = store.items.filter(item1 => item1.id !== item.id)
            store.setItems(updatedItems)
         } else if (item.parent_id === currentFolder?.id) {
            store.pushToItems(item)
         }
      }
   }


   if (op_code === 8) { // message update event, for example, when deleting items
      let timeout = 0
      let type = "info"

      if (event.finished) {
         timeout = 3000

         type = "success"
      }
      if (event.error) {
         timeout = 0
         type = "error"
      }

      toast.update(event.task_id, {

         content: i18n.global.t(event.message, event.args),

         options: { timeout: timeout, type: type, draggable: true, closeOnClick: true }

      }, true)
   }

   
   if (op_code === 9) { // message sent event, for example, when bot is being disabled
      let timeout = 0
      let type = "info"
      if (event.finished) {
         timeout = 3000
         type = "success"
      }

      if (event.error) {
         timeout = 0
         type = "error"
      }
      toast(i18n.global.t(event.message, event.args), {
         timeout: timeout, type: type, draggable: true, closeOnClick: true

      })
   }

   if (op_code === 10) { // folder lock status change event
      for (let item of event.data) {
         if (item.parent_id !== currentFolder?.id) return
         store.changeLockStatusAndPasswordCache({folderId: item.id, newLockStatus: item.isLocked, lockFrom: item.lockFrom})
      }
   }

   if (op_code === 11) { // force logout
      if (store.isLogged) {
         logout()
      }
   }

}