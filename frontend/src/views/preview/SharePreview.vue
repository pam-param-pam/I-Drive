<template>
   <CorePreview
     :file="file"
     :subtitles="subtitles"
     :headerButtons="headerButtons"
     @close="onClose"
     @PreviewEvent="onPreviewEvent"
     file-id="" />
</template>

<script>
import CorePreview from "@/views/preview/CorePreview.vue"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { PreviewEvent } from "@/utils/constants.js"
import { getShareSubtitles } from "@/api/share.js"

export default {
   name: "SharePreview",

   components: {
      CorePreview
   },
   props: ["fileId", "token"],
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
            this.addSelected(file)

            if (file.hasSubtitles) {
               this.subtitles = await getShareSubtitles(this.token, this.file.id)

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
            showMoments: false,
            rename: false,
            delete: false,
            download: true,
            info: true
         }
      }
   },

   methods: {
      ...mapActions(useMainStore, ["showHover", "addSelected"]),
      onPreviewEvent({ type, payload }) {
         if (type === PreviewEvent.MEDIA_PLAY) {

         } else if (type === PreviewEvent.MEDIA_PAUSE) {

         } else if (type === PreviewEvent.MEDIA_SEEK) {
            this.sendShareEvent({ type: "movie_seek", args: { "to_second": payload.toSeconds, "file_id": this.file.id } })
         } else if (type === PreviewEvent.MEDIA_VOLUME_CHANGE) {

         } else if (type === PreviewEvent.MEDIA_TIME_UPDATE) {
            this.sendShareEvent({ "type": "movie_watch", "args": { "timestamp": payload.timestamp, "file_id": this.file.id } })
         } else if (type === PreviewEvent.FULLSCREEN_CHANGE) {

         } else if (type === PreviewEvent.SUBTITLE_CHANGE) {

         }
      },
      sendShareEvent(data) {
         this.shareSocket.send(JSON.stringify(data))
      },
      onClose() {
         try {
            this.$router.push({ name: "Share", params: { ...this.$route.params } })
            // catch every error so user can always close...
         } catch (e) {
            console.error(e)
            this.$router.push({ name: `Share`, params: { folderId: this.user.root } })
         }
      }
   },
}
</script>