import {baseWS} from "@/utils/constants.js"
import {useMainStore} from "@/stores/mainStore.js"


const store = useMainStore()

export default function command(url, command, onmessage, onclose) {
   url = `${baseWS}/command`
   const token = localStorage.getItem("token")

   let conn = new window.WebSocket(url, token)
   let current_folder = store.currentFolder
   conn.onopen = () => conn.send(JSON.stringify({command: command, current_folder_id: current_folder?.id}))
   conn.onmessage = onmessage
   conn.onclose = onclose
}
