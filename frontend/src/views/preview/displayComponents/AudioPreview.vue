<template>
   <div style="height: 100%">
      <img v-if="thumbSrc" :src="thumbSrc" class="cover" />

      <audio
         ref="audio"
         :autoplay="true"
         :src="src"
         controls
         @timeupdate="audioTimeUpdate"
         @error="onError"
      ></audio>
   </div>
</template>

<script>
import { PreviewEvent } from "@/utils/constants.js"
import { backendInstance } from "@/axios/networker.js"

export default {
   props: ["file", "src", "thumbSrc", "mediaPosition"],
   emits: ["previewEvent", "error"],

   data() {
      return {
         lastSentMediaPosition: 0,
         audioRef: null
      }
   },

   mounted() {
      this.audioRef = this.$refs.audio

      if (!this.audioRef) return
      this.audioRef.currentTime = this.mediaPosition || 0
      this.lastSentMediaPosition = this.mediaPosition || 0

   },

   watch: {
      mediaPosition() {
         if (this.mediaPosition)
            this.videoRef.currentTime = this.mediaPosition
         this.lastSentMediaPosition = this.mediaPosition
      }
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
      },
      onError() {
         backendInstance.get(this.src, {
            headers: {
               Range: `bytes=0-1`
            },
            __skipAuth: true,
            baseURL: ""
         })
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