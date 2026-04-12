<template>
   <div style="height: 100%">
      <img v-if="file?.thumbnail_url" :src="file.thumbnail_url" class="cover" />

      <audio
         ref="audio"
         :autoplay="true"
         :src="audioSrcUrl"
         controls
         @timeupdate="audioTimeUpdate"
      ></audio>
   </div>
</template>

<script>
import { PreviewEvent } from "@/utils/constants.js"

export default {
   props: ["file"],
   emits: ["previewEvent", "error"],

   data() {
      return {
         lastSentMediaPosition: 0,
         audioRef: null
      }
   },

   computed: {
      audioSrcUrl() {
         return this.file?.download_url + "?inline=True"
      }
   },

   mounted() {
      this.audioRef = this.$refs.audio

      if (!this.audioRef) return
      this.audioRef.currentTime = this.file.media_position || 0
      this.lastSentMediaPosition = this.file.media_position || 0

   },

   methods: {
      sendPreviewEvent(type, payload = {}) {
         this.$emit("previewEvent", {type, payload})
      },
      audioTimeUpdate() {
         if (!this.audioRef) return

         let position = Math.floor(this.audioRef.currentTime)

         if (Math.abs(position - this.lastSentMediaPosition) >= 10) {
            this.sendPreviewEvent(PreviewEvent.MEDIA_TIME_UPDATE, { timestamp: position })
            this.lastSentMediaPosition = position
         }
      }
   }
}
</script>

<style scoped>
.cover {
  max-width: 100%;
  max-height: 50%;
  display: block;
  margin: 0 auto;
}
</style>