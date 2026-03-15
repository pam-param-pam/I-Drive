<template>
   <div
      id="previewer"
      v-touch:swipe.left="onSwipeLeft"
      v-touch:swipe.right="onSwipeRight"
      @mousemove="toggleNavigation"
      @touchstart="toggleNavigation"
   >
      <header-bar :showLogo="false">
         <action :label="$t('buttons.close')" icon="close" @action="close()" />
         <title v-if="file">{{ file?.name }}</title>
         <title v-else></title>

         <template #actions>
            <action
               v-if="isEpub"
               :label="$t('buttons.decreaseFontSize')"
               icon="remove"
               @action="decreaseFontSize"
            />
            <action
               v-if="file?.type === 'Image' && file?.thumbnail_url"
               :icon="imageFullSize ? 'fullscreen_exit' : 'fullscreen'"
               :label="$t('buttons.toggleSize')"
               @action="imageFullSize = !imageFullSize"
            />
            <action
               v-if="isEpub"
               :label="$t('buttons.increaseFontSize')"
               icon="add"
               @action="increaseFontSize"
            />
            <action
               v-if="file?.type === 'Video' && file?.size > 0 && !isInShareContext"
               :disabled="disabledMoments"
               :label="$t('buttons.moments')"
               icon="bookmarks"
               @action="showMoments"
            />
            <action
               v-if="perms?.modify && !isInShareContext"
               :disabled="loading || error"
               :label="$t('buttons.rename')"
               icon="mode_edit"
               @action="rename()"
            />
            <action
               v-if="perms?.delete && !isInShareContext"
               id="delete-button"
               :disabled="loading || error"
               :label="$t('buttons.moveToTrash')"
               icon="delete"
               @action="moveToTrash"
            />
            <action
               v-if="perms?.download || isInShareContext"
               :disabled="loading || error"
               :label="$t('buttons.download')"
               icon="file_download"
               @action="download"
            />
            <action
               :disabled="loading || error"
               :label="$t('buttons.info')"
               icon="info"
               show="info" />
         </template>
      </header-bar>

      <div v-if="loading" class="loading delayed">
         <div class="spinner">
            <div class="bounce1"></div>
            <div class="bounce2"></div>
            <div class="bounce3"></div>
         </div>
      </div>
      <template v-else>
         <div class="preview">
            <errors v-if="error" :error="error" :simple="false" @close="close" />

            <video
               v-else-if="file?.type === 'Video' && file?.size > 0"
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

            <div v-else-if="isEpub" class="epub-reader">
               <vue-reader
                  :epubInitOptions="{ openAs: 'epub' }"
                  :getRendition="getRendition"
                  :location="bookLocation"
                  :tocChanged="tocChanged"
                  :url="fileSrcUrl"
                  @update:location="locationChange"
               >
               </vue-reader>
               <div class="page">
                  {{ page }}
               </div>
            </div>

            <ExtendedImage
               v-else-if="(file?.type === 'Image' || (file?.type === 'Raw image' && file?.thumbnail_url)) && file?.size > 0"
               :imageFullSize="imageFullSize"
               :src="fileSrcUrl"
               :thumbSrc="thumbSrcUrl"
            />
            <div v-else-if="file?.type === 'Audio' && file?.size > 0" style="height: 100%">
               <img v-if="file?.thumbnail_url" :src="file?.thumbnail_url" class="cover" />
               <audio
                  ref="player"
                  :autoplay="true"
                  :src="videoSrcUrl"
                  controls
               ></audio>
            </div>

            <object
               v-else-if="file?.name.endsWith('.pdf') && file?.size > 0"
               :data="fileSrcUrl"
               class="pdf"
               @error="onPdfError"
            ></object>

            <OfficePreview
               v-else-if="file?.name.endsWith('.docx') && file?.size > 0"
               :file="file"
               :file-url="fileSrcUrl"
            />
            <div v-else-if="file" class="info">
               <div class="title">
                  <i class="material-icons">feedback</i>
                  {{ $t("files.noPreview") }}
               </div>
               <div>
                  <a
                     :href="file?.download_url"
                     class="button button--flat"
                     download
                     target="_blank"
                  >
                     <div>
                        <i class="material-icons">file_download</i>{{ $t("buttons.download") }}
                     </div>
                  </a>
                  <a :href="fileSrcUrl" class="button button--flat" target="_blank">
                     <div>
                        <i class="material-icons">open_in_new</i>{{ $t("buttons.openFile") }}
                     </div>
                  </a>
               </div>
            </div>

         </div>
      </template>

      <button
         :aria-label="$t('buttons.previous')"
         :class="{ hidden: !hasPrevious || !showNav }"
         :title="$t('buttons.previous')"
         @click="prev"
         @mouseleave="hoverNav = false"
         @mouseover="hoverNav = true"
      >
         <i class="material-icons">chevron_left</i>
      </button>
      <button
         :aria-label="$t('buttons.next')"
         :class="{ hidden: !hasNext || !showNav }"
         :title="$t('buttons.next')"
         @click="next"
         @mouseleave="hoverNav = false"
         @mouseover="hoverNav = true"
      >
         <i class="material-icons">chevron_right</i>
      </button>
   </div>
</template>

<script>
import throttle from "lodash.throttle"
import HeaderBar from "@/components/header/HeaderBar.vue"
import Action from "@/components/header/Action.vue"
import { getFile, getSubtitles, updateVideoPosition } from "@/api/files.js"
import { getItems } from "@/api/folder.js"
import { getShare, getShareSubtitles } from "@/api/share.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { defineAsyncComponent } from "vue"
import { backendInstance } from "@/axios/networker.js"
import { deviceControl } from "@/utils/deviceControl.js"
import Errors from "@/components/Errors.vue"
import { baseWS, WebsocketEvent } from "@/utils/constants.js"
import axios from "axios"

export default {
   name: "preview",

   components: {
      Errors,
      OfficePreview: defineAsyncComponent(() =>
         import("@/components/listing/OfficePreview.vue")
      ),
      VueReader: defineAsyncComponent(() =>
         import("vue-reader")
      ),
      ExtendedImage: defineAsyncComponent(() =>
         import("@/components/listing/ExtendedImage.vue")
      ),
      HeaderBar,
      Action

   },

   props: {
      fileId: {
         type: String,
         required: true
      },
      token: {
         type: String
      },
      folderId: {
         type: String
      }
   },

   data() {
      return {
         loading: false,
         fullSize: false,
         showNav: true,
         file: null,
         navTimeout: null,
         hoverNav: false,

         //epub reader data
         bookLocation: null,
         firstRenderDone: false,
         page: null,
         size: null,
         rendition: null,
         toc: [],
         fontSize: 100,

         lastSentVideoPosition: 0,
         prefetchTimeout: null,
         videoRef: null,

         disabledMoments: true,

         subtitles: [],
         imageFullSize: false,

         isFullscreen: false,
         shareSocket: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["error", "sortedItems", "user", "selected", "perms", "currentFolder", "currentPrompt"]),
      isEpub() {
         return this.file?.name.endsWith(".epub")
      },
      isInShareContext() {
         return this.token !== undefined
      },
      thumbSrcUrl() {
         return this.file?.thumbnail_url
      },
      videoSrcUrl() {
         return this.file?.download_url + "?inline=True"
      },
      fileSrcUrl() {
         return this.file?.download_url + "?download=true&inline=True"
      },
      currentIndex() {
         if (this.files && this.file) {
            return this.files.findIndex((item) => item.id === this.file.id)
         }
         return -1
      },
      files() {
         let files = []

         if (this.sortedItems != null) {
            this.sortedItems.forEach((item) => {
               if (!item.isDir && item.type !== "text" && item.type !== "application") {
                  files.push(item)
               }
            })
         }

         return files
      },
      hasNext() {
         return this.currentIndex < this.files.length - 1 // list starts at 0 lul
      },
      hasPrevious() {
         return this.files.length > 1 && this.currentIndex > 0
      },
      disableSwipe() {
         return this.file?.type === "Image"
      }
   },

   watch: {
      '$route'() {
         this.fetchData()
         this.toggleNavigation()
         if (this.prefetchTimeout) clearTimeout(this.prefetchTimeout)
         this.prefetch()
      },
   },

   created() {
      this.fetchData()

      if (this.isInShareContext) {
         // Open new WebSocket
         this.shareSocket = new WebSocket(`${baseWS}/share`, this.token)
         this.shareSocket.onerror = (error) => {
            console.error("shareSocket WebSocket error", error)
         }
      }
   },

   async mounted() {
      window.addEventListener("keydown", this.key)
      window.addEventListener("fullscreenchange", this.fullscreenChange)
   },

   beforeUnmount() {
      window.removeEventListener("keydown", this.key)
      window.removeEventListener("fullscreenchange", this.fullscreenChange)
      if (this.videoRef?.textTracks) {
         this.videoRef.textTracks.removeEventListener("change", this.onSubtitleChanged)

      }
   },

   methods: {
      ...mapActions(useMainStore, ["setTextError", "setCurrentFolderData", "setLastItem", "setError", "setItems", "setCurrentFolder", "addSelected", "showHover", "closeHover"]),
      setLoading(value) {
         this.loading = value
      },
      async fetchData() {
         this.setError(null)

         this.videoRef = null
         this.disabledMoments = true
         // Ensure file is updated in the DOM
         this.file = null
         await this.$nextTick() //this is very important
         if (this.sortedItems) {
            for (let i = 0; i < this.sortedItems.length; i++) {
               if (this.sortedItems[i].id === this.fileId) {
                  this.file = this.sortedItems[i]
                  break
               }
            }
         }

         if (!this.file) {
            try {
               this.setLoading(true)

               if (this.isInShareContext) {
                  let res = await getShare(this.token, this.folderId)
                  this.shareObj = res
                  let items = res.share
                  for (let i = 0; i < items.length; i++) {
                     if (items[i].id === this.fileId) {
                        this.file = items[i]
                     }
                  }
                  if (!this.file) {
                     this.setTextError(404, "Resource not found")
                     return
                  }
                  // Only update store if it is empty
                  if (!this.sortedItems || this.sortedItems.length === 0) {
                     this.setItems(res.share)
                  }
                  this.sendShareEvent({ "type": "file_open", "args": { "file_id": this.file.id } })

               } else {
                  this.file = await getFile(this.fileId, this.lockFrom)
                  if (!this.currentFolder) {
                     let res = await getItems(this.file.parent_id, this.file.lockFrom)
                     this.setCurrentFolderData(res)
                  }
               }
            } catch (error) {
               if (axios.isCancel(error)) return
               this.setError(error)
            } finally {
               this.setLoading(false)
            }
         }

         console.log("MOUNTED FOR FILE: " + this.file.name)

         this.addSelected(this.file)
         this.setLastItem(this.file)

         await this.$nextTick() //this is vevy important
         if (this.file?.type === "Video" && this.$refs.video) {
            this.videoRef = this.$refs.video

            if (!this.isInShareContext) {
               this.videoRef.currentTime = this.file.video_position || 0
               this.lastSentVideoPosition = this.file.video_position || 0
            }

            await this.fetchSubtitles()
            this.loadSubtitleStyle()
            if (!this.videoRef.textTracks) return
            this.videoRef.textTracks.addEventListener("change", this.onSubtitleChanged)
         }

         if (!this.isEpub) return
         this.bookLocation = localStorage.getItem("book-progress-" + this.file.id)
         let fontsize = localStorage.getItem("font-size")
         this.fontSize = fontsize < 600 ? fontsize : 100
      },

      moveToTrash() {
         this.showHover({
            prompt: "moveToTrash",
            confirm: () => {
               this.close()
            }
         })
      },
      onVideoLoaded() {
         this.disabledMoments = false
      },
      async onVideoError() {
         await backendInstance.get(this.file.download_url)
         this.$toast.error(this.$t("toasts.videoUnplayable"))
      },

      onPdfError(error) {
         this.setTextError(500, "Failed to load pdf file. Reason unknown")
      },
      showMoments() {
         if (!this.videoRef.readyState) {
            this.$toast.error(this.$t("toasts.playVideoFirst"))
            return
         }
         this.videoRef.pause()

         this.showHover({
            prompt: "moments",
            props: { video: this.videoRef }

         })
      },
      rename() {
         this.showHover({
            prompt: "rename",
            confirm: (name) => {
               this.file.name = name
            }
         })
      },
      isVideoFullScreen() {
         return this.isFullscreen
      },
      prev() {
         if (this.isVideoFullScreen()) return
         this.hoverNav = false
         if (!this.hasPrevious) return

         const previousFile = this.files[this.currentIndex - 1]

         this.$router.push({
            name: this.isInShareContext ? "SharePreview" : "Preview",
            params: {
               ...this.$route.params,
               fileId: previousFile.id
            }
         })
      },

      next() {
         if (this.isVideoFullScreen()) return
         this.hoverNav = false
         if (!this.hasNext) return

         const nextFile = this.files[this.currentIndex + 1]

         this.$router.push({
            name: this.isInShareContext ? "SharePreview" : "Preview",
            params: {
               ...this.$route.params,
               fileId: nextFile.id
            }
         })
      },
      onSwipeLeft(event) {
         if (this.disableSwipe) return
         this.next()
      },
      onSwipeRight(event) {
         if (this.disableSwipe) return
         this.prev()
      },
      async prefetch() {
         //todo make it better!
         this.prefetchTimeout = setTimeout(() => {
            let file1 = this.files[this.currentIndex + 1]
            let file2 = this.files[this.currentIndex + 2]
            let thumb_url1 = file1?.thumbnail_url
            let thumb_url2 = file2?.thumbnail_url

            if (thumb_url1) {
               let img1 = new Image()
               img1.src = thumb_url1
            }
            if (thumb_url2) {
               let img2 = new Image()
               img2.src = thumb_url2
            }

            if (file1?.type === "video") {
               let video_url = file1?.download_url
               if (video_url) {
                  let videoPlayer = document.createElement("video")
                  videoPlayer.src = video_url
               }
            }
         }, 250)
      },

      key(event) {
         if (this.currentPrompt !== null) {
            return
         }

         if (event.which === 13 || event.which === 39) {
            // right arrow
            this.next()
         } else if (event.which === 37) {
            // left arrow
            this.prev()
         } else if (event.which === 27) {
            // esc
            this.close()
         }
      },

      async fetchSubtitles() {
         try {
            if (!this.isInShareContext) {
               this.subtitles = await getSubtitles(this.file.id, this.file.lockFrom)
            } else {
               this.subtitles = await getShareSubtitles(this.token, this.file.id)
            }
         } catch (err) {
            if (!axios.isCancel(err)) {
               console.error("Subtitle fetch failed", err)
            }
         }
      },
      toggleNavigation: throttle(function() {
         this.showNav = true

         if (this.navTimeout) {
            clearTimeout(this.navTimeout)
         }

         this.navTimeout = setTimeout(() => {
            this.showNav = this.hoverNav
            this.navTimeout = null
         }, 1500)
      }, 500),

      close() {
         let routeName = "Files"
         if (this.isInShareContext) routeName = "Share"
         try {
            this.$router.push({
               name: routeName,
               params: { ...this.$route.params }
            })
            // catch every error so user can always close...
         } catch (e) {
            console.error(e)
            this.$router.push({ name: `Files`, params: { folderId: this.user.root } })
         }
      },

      download() {
         window.open(this.selected[0].download_url + "?download=true", "_blank")
         let message = this.$t("toasts.downloadingSingle", { name: this.selected[0].name })
         this.$toast.success(message)
      },

      videoTimeUpdate() {
         if (!this.videoRef) return
         let position = Math.floor(this.videoRef.currentTime) // round to seconds
         if (Math.abs(position - this.lastSentVideoPosition) >= 10) {

            if (this.isInShareContext) {
               this.sendShareEvent({ "type": "movie_watch", "args": { "timestamp": Math.round(position), "file_id": this.file.id } })
            } else if (this.videoRef.duration > 120) {
               updateVideoPosition(this.file.id, this.file.lockFrom, { position })
            }
            this.lastSentVideoPosition = position
         }
      },
      onMovieSeek() {
         if (!this.videoRef) return
         let toSecond = this.videoRef.currentTime
         if (this.isInShareContext) {
            this.sendShareEvent({ type: "movie_seek", args: { "to_second": Math.round(toSecond), "file_id": this.file.id } })
            return
         }
         deviceControl.sendMovieSeekEvent(toSecond)
      },

      onMovieVolumeChange: throttle(function() {
         if (!this.videoRef) return
         if (this.isInShareContext) return
         let volume = Math.floor(this.videoRef.volume)
         deviceControl.sendMovieVolumeChangeEvent(volume)
      }, 500),

      onMoviePlay() {
         if (!this.videoRef) return
         if (this.isInShareContext) return
         deviceControl.sendMovieToggleEvent(false)
         let toSecond = this.videoRef.currentTime
         deviceControl.sendMovieSeekEvent(toSecond)
      },

      onMoviePause() {
         if (!this.videoRef) return
         if (this.isInShareContext) return
         deviceControl.sendMovieToggleEvent(false)
         let toSecond = this.videoRef.currentTime
         deviceControl.sendMovieSeekEvent(toSecond)
      },

      fullscreenChange() {
         if (!this.videoRef) return
         if (this.isInShareContext) return

         this.isFullscreen = !this.isFullscreen
         deviceControl.sendMovieFullscreenToggleEvent(this.isFullscreen)
      },

      onSubtitleChanged() {
         if (!this.videoRef) return
         if (this.isInShareContext) return

         let tracks = this.videoRef.textTracks

         for (let i = 0; i < tracks.length; i++) {
            let t = tracks[i]
            if (t.mode === "showing") {
               deviceControl.sendMovieSubtitlesChangeEvent(i)
               return
            }
         }
         deviceControl.sendMovieSubtitlesChangeEvent(null)
      },

      toggleFullscreen(isFullscreen) {
         if (isFullscreen) {
            this.videoRef.requestFullscreen()
         } else if (this.isFullscreen) {
            document.exitFullscreen()
         }
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
         if (!style) {
            this.removeSubtitleStyle()
            return
         }
         let subtitleStyle = JSON.parse(style)
         if (subtitleStyle.default) {
            this.removeSubtitleStyle()
            return
         }
         let css = `
            video::cue {
                font-size: ${subtitleStyle.fontSize}px !important;
                color: ${subtitleStyle.color} !important;
                background-color: ${subtitleStyle.backgroundColor} !important;
                text-shadow: ${subtitleStyle.textShadow} !important;
            }
        `
         this.removeSubtitleStyle()

         // Inject new style
         let styleTag = document.createElement("style")
         styleTag.id = "subtitle-style-cue"
         styleTag.innerHTML = css
         document.head.appendChild(styleTag)
      },
      removeSubtitleStyle() {
         let existing = document.getElementById("subtitle-style-cue")
         if (existing) existing.remove()
      },
      getRendition(rendition) {
         this.rendition = rendition
         this.applyStyles()
      },

      applyStyles() {
         if (this.rendition) {
            this.rendition.themes.default({
               body: {
                  "font-size": `${this.fontSize}%`
               }
            })
            this.rendition.flow("paginated") // For continuous scrolling
         }
      },

      increaseFontSize() {
         if (this.fontSize < 500) {
            this.fontSize += 20
            localStorage.setItem("font-size", this.fontSize)
            this.applyStyles()
         }
      },

      calcCurrentLocation() {
         let { displayed } = this.rendition.location.start
         let percentage = Math.round((displayed.page / displayed.total) * 100)
         this.page = `${percentage}% finished • ${displayed.total - displayed.page} pages left in this chapter`
      },

      decreaseFontSize() {
         if (this.fontSize > 60) {
            this.fontSize -= 20
            localStorage.setItem("font-size", this.fontSize)
            this.applyStyles()
         }
      },

      tocChanged(toc) {
         this.toc = toc
      },

      locationChange(epubcifi) {
         this.calcCurrentLocation()
         //todo one day fix padding and location and mobile support etc

         localStorage.setItem("book-progress-" + this.file.id, epubcifi)
         this.bookLocation = epubcifi
      },
      sendShareEvent(data) {
         this.shareSocket.send(JSON.stringify(data))
      }
   },

   sockets: {
      onmessage(message_event) {
         if (this.isInShareContext) return
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
<style scoped>
.page {
  position: fixed;
  left: 50%;
  padding: 10px;
  transform: translateX(-50%);
  color: #5e727e;
  z-index: 1;
  font-size: 12px;
}

.epub-reader {
  display: flex;
  align-items: flex-end;
  height: 100%;
  -webkit-column-break-before: always;
  break-before: column;
}

.epub-reader .arrow.pre {
  left: 0;
}

.epub-reader .size {
  display: flex;
  gap: 5px;
  align-items: center;
  z-index: 111;
  right: 25px;
  outline: none;
  position: absolute;
  top: 78px;
}

/* Mobile-specific styles */
@media (max-width: 768px) {
  .epub-reader .arrow {
    font-size: 1.5rem;
  }

  .epub-reader .arrow.pre {
    left: 0;
  }

  .epub-reader .arrow.next {
    right: 0;
  }
}

html body {
  padding-left: 1px !important;
}

.thumbnail {
  height: 100%;
}
</style>
