import app from "@/main.js"
import { useMainStore } from "@/stores/mainStore.js"

export function isDeviceControlActive() {
   const store = useMainStore()
   const { status, expiry } = store.deviceControlStatus || {}

   if (status !== "active_master") return false

   const now = Math.floor(Date.now() / 1000)
   return expiry > now
}
export function send_route_change_event(route) {
   if (isDeviceControlActive()) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "route_change", args: { route } }
      })
   }
}

export function send_movie_toggle_event(isPaused) {
   if (isDeviceControlActive()) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_toggle", args: { isPaused } }
      })
   }
}

export function send_movie_seek_event(seconds) {
   if (isDeviceControlActive()) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_seek", args: { seconds } }
      })
   }
}

export function send_movie_volume_change_event(volume) {
   if (isDeviceControlActive()) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_volume_change", args: { volume } }
      })
   }
}
