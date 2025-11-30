import app from "@/main.js"
import { useMainStore } from "@/stores/mainStore.js"

export function send_route_change_event(route) {
   const store = useMainStore()
   if (store.deviceControlStatus.status === "active_master") {
      app.config.globalProperties.$socket.send_obj({ op_code: 15, message: { "type": "route_change", "args": { "route": route } } })
   }
}

export function send_movie_toggle_event(isPaused) {
   const store = useMainStore()
   if (store.deviceControlStatus.status === "active_master") {
      app.config.globalProperties.$socket.send_obj({ op_code: 15, message: { "type": "movie_toggle", "args": { "isPaused": isPaused } } })
   }
}

export function send_movie_seek_event(seconds) {
   const store = useMainStore()
   if (store.deviceControlStatus.status === "active_master") {
      app.config.globalProperties.$socket.send_obj({ op_code: 15, message: { "type": "movie_seek", "args": { "seconds": seconds } } })
   }
}

export function send_movie_volume_change_event(volume) {
   const store = useMainStore()
   if (store.deviceControlStatus.status === "active_master") {
      app.config.globalProperties.$socket.send_obj({ op_code: 15, message: { "type": "movie_volume_change", "args": { "volume": volume } } })
   }
}