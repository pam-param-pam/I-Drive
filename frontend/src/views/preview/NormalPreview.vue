<template>
   <CorePreview
     :file="file"
     :subtitles="subtitles"
     :mediaPosition="mediaPosition"
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
import { getMediaPositions, getSubtitles, updateMediaPosition } from "@/api/files.js"
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
         subtitles: null,
         mediaPositions: [],
         checkedMediaPositionIds: new Set(),
         loadingMediaPositionIds: new Set()
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

            await this.fetchMediaPositionIfNeeded(file)
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

      mediaPosition() {
         if (!this.file) return null
         let pos = this.mediaPositions.find(mediaPosition => mediaPosition.file_id === this.file.id)
         if (pos) {
            return pos.timestamp
         }
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
      async fetchMediaPositionIfNeeded(file) {
         if (
           this.checkedMediaPositionIds.has(file.id) ||
           this.loadingMediaPositionIds.has(file.id)
         ) return

         const currentIndex = this.sortedItems.findIndex(item => item.id === file.id)
         if (currentIndex === -1) return

         const fileIds = this.sortedItems
           .slice(Math.max(0, currentIndex - 45), currentIndex + 45)
           .map(item => item.id)

         fileIds.forEach(id => this.loadingMediaPositionIds.add(id))

         try {
            const positions = await getMediaPositions({ ids: fileIds })

            for (const position of positions) {
               const existing = this.mediaPositions.find(
                 pos => pos.file_id === position.file_id
               )

               if (existing) {
                  Object.assign(existing, position)
               } else {
                  this.mediaPositions.push(position)
               }
            }

            fileIds.forEach(id => this.checkedMediaPositionIds.add(id))
         } finally {
            fileIds.forEach(id => this.loadingMediaPositionIds.delete(id))
         }
      },
      upsertMediaPosition(fileId, position) {
         const mediaPosition = this.mediaPositions.find(mediaPosition => mediaPosition.file_id === fileId)

         if (mediaPosition) {
            mediaPosition.position = position
            return
         }

         this.mediaPositions.push({file_id: fileId, position})
      },

      onPreviewEvent({ type, payload }) {
         if (type === PreviewEvent.MEDIA_TIME_UPDATE) {
            const position = payload.timestamp

            this.upsertMediaPosition(this.file.id, position)
            updateMediaPosition(this.file.id, this.file.lockFrom, { position })
         }
      },

      onClose() {
         this.$router.replace({ name: "Files", params: { ...this.$route.params } })
      }
   }
}
</script>