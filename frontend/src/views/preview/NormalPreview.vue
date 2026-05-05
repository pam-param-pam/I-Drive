<template>
   <CorePreview
      :file="file"
      :subtitles="subtitles"
      :headerButtons="headerButtons"
      @close="onClose"
      @PreviewEvent="onPreviewEvent"
   />
</template>

<script>
import CorePreview from "@/views/preview/CorePreview.vue"
import { useMainStore } from "@/stores/mainStore.js"
import { mapState } from "pinia"
import { getSubtitles, updateMediaPosition } from "@/api/files.js"
import { PreviewEvent, WebsocketEvent } from "@/utils/constants.js"

export default {
   name: "NormalPreview",

   components: {
      CorePreview
   },
   props: ["fileId"],
   data() {
      return {
         subtitles: null
      }

   },
   watch: {
      file: {
         immediate: true,
         async handler(file) {
            if (!file) return
            if (file.hasSubtitles) {
               this.subtitles = await getSubtitles(file.id, file.lockFrom)

            }
         }
      }
   },
   computed: {
      ...mapState(useMainStore, ["sortedItems", "perms"]),

      file() {
         if (!this.sortedItems) return null
         return this.sortedItems.find(f => f.id === this.fileId)
      },
      headerButtons() {
         return {
            toggleImageFullSize: true,
            showMoments: this.perms?.modify,
            rename: this.perms?.modify,
            delete: this.perms?.modify,
            download: this.perms?.download,
            info: true
         }
      }
   },

   methods: {
      onPreviewEvent({ type, payload }) {
         if (type === PreviewEvent.MEDIA_PLAY) {
         } else if (type === PreviewEvent.MEDIA_PAUSE) {
         } else if (type === PreviewEvent.MEDIA_SEEK) {
         } else if (type === PreviewEvent.MEDIA_VOLUME_CHANGE) {
         } else if (type === PreviewEvent.MEDIA_TIME_UPDATE) {
            updateMediaPosition(this.file.id, this.file.lockFrom, {position: payload.timestamp})
         } else if (type === PreviewEvent.FULLSCREEN_CHANGE) {
         } else if (type === PreviewEvent.SUBTITLE_CHANGE) {
         }
      },
      onClose() {
         this.$router.replace({ name: "Files", params: { ...this.$route.params } })
      }
   },
   sockets: {
      onmessage(message_event) {
         //send commands downward
         if (message_event.data === "PING") return
         let jsonObject = JSON.parse(message_event.data)
         let event = jsonObject.event
         let op_code = event.op_code

         if (op_code === WebsocketEvent.DEVICE_CONTROL_COMMAND) {
            let type = event.data[0].type
            let args = event.data[0].args

            if (type === "movie_seek") {
               this.videoRef.currentTime = args.seconds
            } else if (type === "movie_toggle") {
               let isPaused = args.isPaused
               if (isPaused) this.videoRef.pause()
               else this.videoRef.play()
            } else if (type === "movie_volume_change") {
               this.videoRef.volume = args.volume
            } else if (type === "movie_fullscreen_toggle") {
               this.toggleFullscreen(args.is_fullscreen)
            } else if (type === "movie_subtitle_change") {
               this.setSubtitleTrack(args.subtitle_id)
            }
         }
      }
   }
}
</script>