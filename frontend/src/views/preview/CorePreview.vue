<template>
   <div
      id="previewer"
      v-touch:swipe.left="onSwipeLeft"
      v-touch:swipe.right="onSwipeRight"
      v-touch:swipe.top="onSwipeTop"
      v-touch:swipe.bottom="onSwipeBottom"
      @mousemove="toggleNavigation"
      @touchstart="toggleNavigation"
   >
      <header-bar :showLogo="false">
         <action :label="$t('buttons.close')" icon="close" @action="close" />
         <title v-if="file">{{ file?.name }}</title>
         <title v-else></title>

         <template #actions>
            <action
               v-if="headerButtons.toggleImageFullSize && file?.type === 'Image' && file?.thumbnail_url"
               :icon="imageFullSize ? 'fullscreen_exit' : 'fullscreen'"
               :label="$t('buttons.toggleSize')"
               @action="imageFullSize = !imageFullSize"
            />
            <action
              v-if="headerButtons.showMoments && file?.type === 'Video' && notEmpty"
               :disabled="disabledMoments"
               :label="$t('buttons.moments')"
               icon="bookmarks"
               @action="showMoments"
            />
            <action
              v-if="headerButtons.rename"
               :disabled="loading || error"
               :label="$t('buttons.rename')"
               icon="mode_edit"
               @action="rename()"
            />
            <action
              v-if="headerButtons.delete"
               id="delete-button"
               :disabled="loading || error"
               :label="$t('buttons.moveToTrash')"
               icon="delete"
               @action="moveToTrash"
            />
            <action
              v-if="headerButtons.download"
               :disabled="loading || error"
               :label="$t('buttons.download')"
               icon="file_download"
               @action="download"
            />
            <action
               v-if="headerButtons.download"
               :disabled="loading || error"
               :label="$t('buttons.info')"
               icon="info"
               show="info" />
         </template>
      </header-bar>

      <loading-spinner v-if="loading" :loading="loading" :show-text="false"/>

      <template v-else>
         <div class="preview">
            <errors v-if="error" :error="error" :simple="false" @close="close" />

            <VideoPreview
              v-else-if="previewerType === 'video'"
              ref="videoPreview"
              :file="file"
              :subtitles="subtitles"
              @previewEvent="onPreviewEvent"
              @error="onPreviewError"
            />

            <EditorPreview
              v-else-if="previewerType === 'editor'"
              :file="file"
              :readonly="readonly"
              @previewEvent="onPreviewEvent"
              @error="onPreviewError"
            />

            <ImagePreview
              v-else-if="previewerType === 'image'"
              :imageFullSize="imageFullSize"
              :src="fileSrcUrl"
              :thumbSrc="thumbSrcUrl"
              @previewEvent="onPreviewEvent"
              @error="onPreviewError"
            />

            <AudioPreview
              v-else-if="previewerType === 'audio'"
              :file="file"
              @previewEvent="onPreviewEvent"
              @error="onPreviewError"
            />

            <PdfPreview
              v-else-if="previewerType === 'pdf'"
              :file="file"
              :src="fileSrcUrl"
              @previewEvent="onPreviewEvent"
              @error="onPreviewError"
            />

            <OfficePreview
              v-else-if="previewerType === 'office'"
              :file="file"
              :file-url="fileSrcUrl"
              @previewEvent="onPreviewEvent"
              @error="onPreviewError"
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
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { defineAsyncComponent } from "vue"
import Errors from "@/components/Errors.vue"
import { PreviewEvent } from "@/utils/constants.js"
import VideoPreview from "@/views/preview/displayComponents/VideoPreview.vue"
import AudioPreview from "@/views/preview/displayComponents/AudioPreview.vue"
import PdfPreview from "@/views/preview/displayComponents/PdfPreview.vue"
import ImagePreview from "@/views/preview/displayComponents/ImagePreview.vue"
import EditorPreview from "@/views/preview/displayComponents/EditorPreview.vue"
import loadingSpinner from "@/components/loadingSpinner.vue"

export default {
   name: "CorePreview",

   emits: ["PreviewEvent", "close"],

   components: {
      loadingSpinner,
      EditorPreview,
      PdfPreview,
      AudioPreview,
      VideoPreview,
      Errors,
      ImagePreview,
      HeaderBar,
      Action,
      OfficePreview: defineAsyncComponent(() =>
         import("@/views/preview/displayComponents/OfficePreview.vue")
      ),
      VueReader: defineAsyncComponent(() =>
         import("vue-reader")
      ),
   },

   props: {
      file: {
         required: true
      },
      headerButtons: {
         required: true,
      },
      subtitles: {
         required: false,
      },
      readonly: {
         required: false,
         default: false,
      }
   },

   data() {
      return {
         error: null,
         fullSize: false,
         showNav: true,
         navTimeout: null,
         hoverNav: false,

         isVideoFullscreen: false,

         prefetchTimeout: null,

         disabledMoments: true,

         imageFullSize: false,

         isFullscreen: false,
         isEditorClean: true,
      }
   },
   watch: {
      file: {
         async handler() {
           this.handleFileChange(false)
         }
      }
   },
   created() {
      this.handleFileChange(true)
   },
   computed: {
      ...mapState(useMainStore, ["itemsLoading", "sortedItems", "user", "selected", "perms", "currentFolder", "currentPrompt"]),
      loading() {
        return this.itemsLoading
      },
      previewerType() {
         if (!this.file) return null

         if (this.file.type === "Video" && this.notEmpty) return "video"

         if ((this.file.type === "Image" || (this.file.type === "Raw image" && this.file.thumbnail_url)) && this.notEmpty) return "image"

         if ((this.file.type === "Audio") && this.notEmpty) return "audio"

         if ((this.file.name?.endsWith(".pdf") && this.notEmpty)) return "pdf"

         if ((this.file.name?.endsWith(".docx")) && this.notEmpty) return "office"

         if (this.file.type === "Code" || this.file.type === "Text" || this.file.type === "Database") return "editor"

         return "unknown"
      },
      notEmpty() {
         return this.file?.size > 0
      },

      thumbSrcUrl() {
         return this.file?.thumbnail_url
      },
      videoSrcUrl() {
         return this.file?.download_url
      },
      fileSrcUrl() {
         return this.file?.download_url
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
         return this.previewerType === "image" || this.previewerType === "editor"
      }
   },

   async mounted() {
      document.addEventListener("keydown", this.key)
      this.onPreviewEvent(PreviewEvent.OPEN)
   },

   unmounted() {
      document.removeEventListener("keydown", this.key)
   },

   methods: {
      ...mapActions(useMainStore, ["setCurrentFolderData", "setLastItem", "setItems", "setCurrentFolder", "addSelected", "showHover", "closeHover"]),
      handleFileChange() {
         this.setError(null)
         if (!this.loading && !this.file) {
            this.setError({code: 404, details: "File not found"})
         }
         this.setLastItem(this.file)
         this.addSelected(this.file)
      },
      onPreviewError(error) {
        this.setError(error)
      },
      setError(value) {
         this.error = value
      },
      onPreviewEvent({type, payload}) {
         if (type === PreviewEvent.MEDIA_LOADED) {
            this.disabledMoments = false
         } else if (type === PreviewEvent.FULLSCREEN_CHANGE) {
            this.isVideoFullscreen = payload.is_fullscreen
         } else if (type === PreviewEvent.EDITOR_CLEAN_CHANGE) {
            console.log("EDITOR_CLEAN_CHANGE")
            console.log(payload.is_clean)
            this.isEditorClean = payload.is_clean
         }
         this.$emit("PreviewEvent", {type, payload})
      },

      moveToTrash() {
         this.showHover({
            prompt: "moveToTrash",
            confirm: () => {
               this.close()
            }
         })
      },

      showMoments() {
         let videoRef = this.$refs.videoPreview.getVideo()
         if (!videoRef) {
            this.$toast.error(this.$t("toasts.playVideoFirst"))
            return
         }
         videoRef.pause()

         this.showHover({
            prompt: "moments",
            props: { video: videoRef }

         })
      },
      rename() {
         this.showHover({
            prompt: "rename"
         })
      },

      download() {
         window.open(this.selected[0].download_url, "_blank")
         let message = this.$t("toasts.downloadingSingle", { name: this.selected[0].name })
         this.$toast.success(message)
         this.onPreviewEvent(PreviewEvent.DOWNLOAD)
      },

      prev() {
         if (this.isVideoFullscreen) return
         this.hoverNav = false
         if (!this.hasPrevious) return

         const previousFile = this.files[this.currentIndex - 1]

         this.$router.push({
            name: this.$route.name,
            params: {
               ...this.$route.params,
               fileId: previousFile.id
            }
         })
      },

      next() {
         if (this.isVideoFullscreen) return
         this.hoverNav = false
         if (!this.hasNext) return

         const nextFile = this.files[this.currentIndex + 1]

         this.$router.push({
            name: this.$route.name,
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
      onSwipeTop(event) {
         if (this.isVideoFullscreen) return
         if (this.disableSwipe) return
         this.showHover("info")
      },
      onSwipeBottom(event) {
         if (this.isVideoFullscreen) return
         if (this.disableSwipe) return
         this.close()
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
         console.log("key event preview")
         console.log(this.currentPrompt)
         if (this.currentPrompt !== null) return

         if (event.which === 13 || event.which === 39) {
            // right arrow
            this.next()
         } else if (event.which === 37) {
            // left arrow
            this.prev()
         } else if (event.which === 27) {
            console.log("closee")
            // esc
            this.close()
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
         if (!this.isEditorClean) {
            this.showHover({
               prompt: "discardEditorChanges",
               confirm: () => {
                  this.$emit('close')
               }
            })
            return
         }
         this.$emit('close')
      }
   },


}
</script>
<style scoped>

html body {
  padding-left: 1px !important;
}

</style>
