<template>
  <div
    id="previewer"
    v-touch:swipe.left="next"
    v-touch:swipe.right="prev"
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
          v-if="isEpub"
          :label="$t('buttons.increaseFontSize')"
          icon="add"
          @action="increaseFontSize"
        />
        <action
          v-if="perms?.modify && !isInShareContext"
          :disabled="loading"
          :label="$t('buttons.rename')"
          icon="mode_edit"
          @action="rename()"
        />
        <action
          v-if="perms?.delete && !isInShareContext"
          id="delete-button"
          :disabled="loading"
          :label="$t('buttons.moveToTrash')"
          icon="delete"
          @action="moveToTrash"
        />
        <action
          v-if="perms?.download || isInShareContext"
          :disabled="loading"
          :label="$t('buttons.download')"
          icon="file_download"
          @action="download"
        />
        <action :disabled="loading" :label="$t('buttons.info')" icon="info" show="info" />
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
        <video
          v-if="file?.type === 'video' && file?.size > 0"
          id="video"
          ref="video"
          :autoplay="autoPlay"
          :poster="file?.thumbnail_url"
          :src="fileSrcUrl"
          controls
          loop
          @play="autoPlay = true"
          @timeupdate="videoTimeUpdate"
        ></video>

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

        <ExtendedImage v-else-if="file?.type === 'image' && file?.size > 0" :src="fileSrcUrl" />
        <div v-else-if="file?.type === 'audio' && file?.size > 0" style="height: 100%">
          <img v-if="file?.thumbnail_url" :src="file?.thumbnail_url" class="cover" />
          <audio
            ref="player"
            :autoplay="autoPlay"
            :src="fileSrcUrl"
            controls
            @play="autoPlay = true"
          ></audio>
        </div>

        <object
          v-else-if="file?.extension === '.pdf' && file?.size > 0"
          :data="fileSrcUrl"
          class="pdf"
        ></object>

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
import { getFile, updateVideoPosition } from "@/api/files.js"
import { getItems } from "@/api/folder.js"
import { getShare } from "@/api/share.js"
import { VueReader } from "vue-reader"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import ExtendedImage from "@/components/listing/ExtendedImage.vue"

export default {
   name: "preview",

   components: {
      HeaderBar,
      VueReader,
      Action,
      ExtendedImage
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
         fullSize: false,
         showNav: true,
         file: null,
         navTimeout: null,
         hoverNav: false,
         autoPlay: true,

         //epub reader data
         bookLocation: null,
         firstRenderDone: false,
         page: null,
         size: null,
         rendition: null,
         toc: [],
         fontSize: 100,
         lastSentVideoPosition: 0,

         prefetchTimeout: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["sortedItems", "user", "selected", "loading", "perms", "currentFolder", "currentPrompt", "isLogged"]),
      isEpub() {
         if (!this.file) return false
         return this.file.extension === ".epub"
      },
      isInShareContext() {
         return this.token !== undefined
      },

      fileSrcUrl() {
         if (this.file?.preview_url) return this.file?.preview_url + "?inline=True"
         return this.file?.download_url + "?inline=True"
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
      }
   },

   watch: {
      $route() {
         this.fetchData()
         this.toggleNavigation()
         if (this.prefetchTimeout) clearTimeout(this.prefetchTimeout)
         this.prefetch()
      }
   },

   created() {
      this.fetchData()
   },

   async mounted() {
      window.addEventListener("keydown", this.key)
   },

   beforeUnmount() {
      window.removeEventListener("keydown", this.key)
   },

   methods: {
      ...mapActions(useMainStore, ["setCurrentFolderData", "setLastItem", "setLoading", "setError", "setItems", "setCurrentFolder", "addSelected", "showHover", "closeHover"]),

      async fetchData() {
         this.setLoading(true)
         this.setError(null)

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
               if (this.isInShareContext) {
                  let res = await getShare(this.token, this.folderId)
                  this.shareObj = res
                  let items = res.share
                  for (let i = 0; i < items.length; i++) {
                     if (items[i].id === this.fileId) {
                        this.file = items[i]
                     }
                  }
                  this.setItems(res.share)
               } else {
                  this.file = await getFile(this.fileId, this.lockFrom)
                  if (!this.currentFolder) {
                     let res = await getItems(this.file.parent_id, this.file.lockFrom)
                     this.setCurrentFolderData(res)
                  }
               }
            } catch (error) {
               if (error.code === "ERR_CANCELED") return
               this.setError(error)
            } finally {
               this.setLoading(false)
            }
         }
         this.addSelected(this.file)
         this.setLastItem(this.file)

         if (this.file?.type === "video" && this.$refs.video) {
            this.$refs.video.currentTime = this.file.video_position || 0
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

      rename() {
         this.showHover({
            prompt: "rename",
            confirm: (name) => {
               this.file.name = name
            }
         })
      },
      isVideoFullScreen() {
         if (this.file.type !== "video") return false
         let videoElement = this.$refs.video
         return document.fullscreenElement === videoElement ||
            document.webkitFullscreenElement === videoElement ||
            document.mozFullScreenElement === videoElement ||
            document.msFullscreenElement === videoElement
      },
      prev() {
         if (this.isVideoFullScreen()) return
         this.hoverNav = false
         if (this.hasPrevious) {
            let previousFile = this.files[this.currentIndex - 1]

            if (this.isInShareContext) {
               this.$router.push({
                  name: "SharePreview",
                  params: {
                     folderId: previousFile.parent_id,
                     fileId: previousFile.id,
                     token: this.token
                  }
               })
            } else {
               this.$router.push({
                  name: "Preview",
                  params: { fileId: previousFile.id, lockFrom: previousFile.lockFrom }
               })
            }
         }
      },

      next() {
         if (this.isVideoFullScreen()) return
         this.hoverNav = false
         if (this.hasNext) {
            let nextFile = this.files[this.currentIndex + 1]

            if (this.isInShareContext) {
               this.$router.push({
                  name: "SharePreview",
                  params: { folderId: nextFile.parent_id, fileId: nextFile.id, token: this.token }
               })
            } else {
               this.$router.push({
                  name: "Preview",
                  params: { fileId: nextFile.id, lockFrom: nextFile.lockFrom }
               })
            }
         }
      },

      async prefetch() {
        //todo make it better!
         this.prefetchTimeout = setTimeout(() => {
            let url1 = this.files[this.currentIndex + 1]?.thumbnail_url
            let url2 = this.files[this.currentIndex + 2]?.thumbnail_url

            if (url1) {
               let img1 = new Image()
               img1.src = url1
            }
            if (url1) {
               let img2 = new Image()
               img2.src = url2
            }
         }, 50)
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

      resetPrompts() {
         this.closeHover()
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
         try {
            let parent_id = this.file?.parent_id

            if (this.isInShareContext) {
               this.$router.push({
                  name: "Share",
                  params: { token: this.token, folderId: this.folderId }
               })
               return
            }
            if (parent_id) {
               this.$router.push({ name: `Files`, params: { folderId: parent_id } })
            } else {
               this.$router.push({ name: `Files`, params: { folderId: this.user.root } })
            }

            // catch every error so user can always close...
         } catch (e) {
            console.error(e)
            this.$router.push({ name: `Files`, params: { folderId: this.user.root } })
         }
      },

      download() {
         window.open(this.selected[0].download_url, "_blank")
         let message = this.$t("toasts.downloadingSingle", { name: this.selected[0].name })
         this.$toast.success(message)
      },

      videoTimeUpdate() {
         if (!this.isLogged) return
         if (!this.$refs.video) {
            console.warn("this.$refs.video is falsy")
            return
         }
         let position = Math.floor(this.$refs.video.currentTime) // round to seconds
         // To prevent sending too many requests, send only if the position has changed significantly
         if (Math.abs(position - this.lastSentVideoPosition) >= 10) {
            // Adjust the interval as needed (e.g., every 1 second)
            updateVideoPosition({ file_id: this.file.id, position: position })

            this.lastSentVideoPosition = position
         }
      },

      getRendition(rendition) {
         // rendition.hooks.content.register((contents) => {
         //   rendition.manager.container.style['scroll-behavior'] = 'smooth'
         // })
         this.rendition = rendition
         // Wait for the content to be fully rendered

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
         // if (isMobile) {
         //   let container = this.rendition.manager.container
         //   console.log(container)
         //   let iframe = container.querySelector('iframe')
         //   console.log(iframe)
         //
         //   if (iframe) {
         //     const iframeDocument = iframe.contentDocument || iframe.contentWindow.document
         //     console.log(iframeDocument)
         //     const body = iframeDocument.querySelector('body')
         //
         //     if (body) {
         //       // Modify body styles directly
         //       body.style.setProperty('padding-left', '30px', 'important')
         //       body.style.setProperty('padding-right', '30px', 'important')
         //       body.style.setProperty('padding-top', '20px', 'important')
         //       body.style.setProperty('padding-bottom', '20px', 'important')
         //     }
         //   }
         // }

         // let container = this.rendition.manager.container
         // console.log(container)
         // let iframe = container.querySelector('iframe')
         // console.log(iframe)
         //
         // if (iframe) {
         //   const iframeDocument = iframe.contentDocument || iframe.contentWindow.document
         //   console.log(iframeDocument)
         //
         //   iframeDocument.addEventListener('scroll', (event) => {
         //     const scrollDirection = event.deltaX < 0 ? 'left' : 'right'
         //     // Handle the scroll direction and adjust navigation accordingly
         //     console.log(`Scrolled ${scrollDirection}`)
         //   })
         // }

         localStorage.setItem("book-progress-" + this.file.id, epubcifi)
         this.bookLocation = epubcifi
      }
   }
}
</script>
<style>
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
