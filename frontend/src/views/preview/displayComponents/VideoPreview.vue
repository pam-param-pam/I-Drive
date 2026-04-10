<template>
   <video
      id="video"
      ref="video"
      :autoplay="true"
      :poster="file?.thumbnail_url"
      :src="videoSrcUrl"
      controls
      crossorigin="anonymous"
      loop
      @error="onVideoError"
      @loadedmetadata="onVideoLoaded"
      @pause="onMoviePause"
      @play="onMoviePlay"
      @seeked="onMovieSeek"
      @timeupdate="videoTimeUpdate"
      @volumechange="onMovieVolumeChange"
   >
      <track
         v-for="(sub) in subtitles"
         :key="sub.id"
         :default="sub.is_forced"
         :label="sub.language"
         :src="sub.url"
         kind="subtitles"
      />
   </video>
</template>

<script>
import throttle from "lodash.throttle"
import { backendInstance } from "@/axios/networker.js"
import { PreviewEvent } from "@/utils/constants.js"

export default {
   props: ["file", "subtitles"],
   emits: ["previewEvent"],
   data() {
      return {
         videoRef: null,
         lastSentMediaPosition: 0,
         isFullscreen: false
      }
   },

   computed: {
      videoSrcUrl() {
         return this.file?.download_url + "?inline=True"
      }
   },

   async mounted() {
      this.videoRef = this.$refs.video

      if (!this.videoRef) return

      if (!this.isInShareContext) {
         this.videoRef.currentTime = this.file.media_position || 0
         this.lastSentMediaPosition = this.file.media_position || 0
      }

      if (this.subtitles) {
         this.loadSubtitleStyle()

         if (this.videoRef.textTracks) {
            this.videoRef.textTracks.addEventListener("change", this.onSubtitleChanged)
         }
      }

      window.addEventListener("fullscreenchange", this.fullscreenChange)
   },

   beforeUnmount() {
      if (this.videoRef?.textTracks) {
         this.videoRef.textTracks.removeEventListener("change", this.onSubtitleChanged)
      }

      window.removeEventListener("fullscreenchange", this.fullscreenChange)
   },

   methods: {
      sendPreviewEvent(type, payload = {}) {
         this.$emit("previewEvent", {type, payload})
      },
      getVideo() {
         return this.videoRef
      },

      onVideoLoaded() {
         this.sendPreviewEvent(PreviewEvent.MEDIA_LOADED)
      },

      async onVideoError() {
         await backendInstance.get(this.file.download_url)
         this.$toast.error(this.$t("toasts.videoUnplayable"))
      },

      videoTimeUpdate() {
         if (!this.videoRef) return

         let position = Math.floor(this.videoRef.currentTime)
         if (Math.abs(position - this.lastSentMediaPosition) >= 10) {
            this.sendPreviewEvent(PreviewEvent.MEDIA_TIME_UPDATE, { timestamp: position })
            this.lastSentMediaPosition = position
         }
      },

      onMovieSeek() {
         if (!this.videoRef) return

         let toSecond = Math.round(this.videoRef.currentTime)
         this.sendPreviewEvent(PreviewEvent.MEDIA_SEEK, { to_second: toSecond })
      },

      onMovieVolumeChange: throttle(function () {
         if (!this.videoRef) return

         let volume = Math.floor(this.videoRef.volume)
         this.sendPreviewEvent(PreviewEvent.MEDIA_VOLUME_CHANGE, { volume: volume })
      }, 500),

      onMoviePlay() {
         if (!this.videoRef) return

         let position = this.videoRef.currentTime
         this.sendPreviewEvent(PreviewEvent.MEDIA_PLAY, { position: position })
      },

      onMoviePause() {
         if (!this.videoRef) return

         let position = this.videoRef.currentTime
         this.sendPreviewEvent(PreviewEvent.MEDIA_PAUSE, { position: position })
      },

      fullscreenChange() {
         if (!this.videoRef || this.isInShareContext) return

         this.isFullscreen = !this.isFullscreen

         this.sendPreviewEvent(PreviewEvent.FULLSCREEN_CHANGE, { is_fullscreen: this.isFullscreen })
      },

      onSubtitleChanged() {
         if (!this.videoRef) return

         let tracks = this.videoRef.textTracks

         for (let i = 0; i < tracks.length; i++) {
            if (tracks[i].mode === "showing") {
               this.sendPreviewEvent(PreviewEvent.SUBTITLE_CHANGE, { index: i })
               return
            }
         }

         this.sendPreviewEvent(PreviewEvent.SUBTITLE_CHANGE, { index: null })
      },

      setSubtitleTrack(index) {
         if (!this.videoRef) return
         if (index === null || index === undefined) return
         let tracks = this.videoRef.textTracks

         for (let i = 0; i < tracks.length; i++) {
            tracks[i].mode = "disabled"
         }

         if (index >= 0 && index < tracks.length) {
            tracks[index].mode = "showing"
         }
      },

      loadSubtitleStyle() {
         let style = localStorage.getItem("subtitleStyle")
         if (!style) return

         let subtitleStyle = JSON.parse(style)
         if (subtitleStyle.default) return

         let css = `
            video::cue {
               font-size: ${subtitleStyle.fontSize}px !important;
               color: ${subtitleStyle.color} !important;
               background-color: ${subtitleStyle.backgroundColor} !important;
               text-shadow: ${subtitleStyle.textShadow} !important;
            }
         `

         let styleTag = document.createElement("style")
         styleTag.innerHTML = css
         document.head.appendChild(styleTag)
      }
   }
}
</script>