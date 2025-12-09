import app from "@/main.js"
import { useMainStore } from "@/stores/mainStore.js"

export function isDeviceControlActive() {
   const store = useMainStore()
   if (!store.deviceControlOptions.isDeviceControlActive) return false
   const { status, expiry } = store.deviceControlStatus || {}

   if (status !== "active_master") return false

   const now = Math.floor(Date.now() / 1000)
   return expiry > now
}
export function send_route_change_event(route) {
   const store = useMainStore()

   if (isDeviceControlActive() && store.deviceControlOptions.isNavigationActive) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "route_change", args: { route } }
      })
   }
}

export function send_movie_toggle_event(isPaused) {
   const store = useMainStore()

   if (isDeviceControlActive() && store.deviceControlOptions.isVideoToggleActive) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_toggle", args: { isPaused } }
      })
   }
}

export function send_movie_seek_event(seconds) {
   const store = useMainStore()

   if (isDeviceControlActive() && store.deviceControlOptions.isVideoSeekActive) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_seek", args: { seconds } }
      })
   }
}

export function send_movie_volume_change_event(volume) {
   const store = useMainStore()

   if (isDeviceControlActive() && store.deviceControlOptions.isVideoVolumeChangeActive) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_volume_change", args: { volume } }
      })
   }
}

export function send_movie_subtitles_change_event(subtitle_id) {
   const store = useMainStore()

   if (isDeviceControlActive() && store.deviceControlOptions.isVideoSubtitlesActive) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_subtitle_change", args: { subtitle_id } }
      })
   }
}

export function send_movie_fullscreen_toggle_event(is_fullscreen) {
   const store = useMainStore()

   if (isDeviceControlActive() && store.deviceControlOptions.isVideoFullscreenActive) {
      app.config.globalProperties.$socket.send_obj({
         op_code: 15,
         message: { type: "movie_fullscreen_toggle", args: { is_fullscreen } }
      })
   }
}