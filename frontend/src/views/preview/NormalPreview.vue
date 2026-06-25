<template>
   <CorePreview
      :file="file"
      :subtitles="subtitles"
      :headerButtons="headerButtons"
      :useSW="useSW"
      @close="onClose"
      @PreviewEvent="onPreviewEvent"
   />
</template>

<script>
import CorePreview from "@/views/preview/CorePreview.vue"
import { useMainStore } from "@/stores/mainStore.js"
import { mapState } from "pinia"
import { getSubtitles, updateMediaPosition } from "@/api/files.js"
import { ClientsideDecryptionMethod, PreviewEvent } from "@/utils/constants.js"
import { isDesktop } from "@/utils/common.js"

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
      ...mapState(useMainStore, ["sortedItems", "perms", "settings"]),
      useSW() {
        return this.settings.clientsideDecryptionMethod === ClientsideDecryptionMethod.ALWAYS ||
          this.settings.clientsideDecryptionMethod === ClientsideDecryptionMethod.DESKTOP_ONLY && isDesktop()
      },
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
   }
}
</script>