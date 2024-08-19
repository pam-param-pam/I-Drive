<template>
  <div
    id="previewer"
    @mousemove="toggleNavigation"
    @touchstart="toggleNavigation"
  >
    <header-bar :showLogo="false">
      <action icon="close" :label="$t('buttons.close')" @action="close()"/>
      <title v-if="file">{{ file.name }}</title>
      <title v-else></title>

      <template #actions>
        <action
          v-if="isEpub"
          icon="remove"
          :label="$t('buttons.decreaseFontSize')"
          @action="decreaseFontSize"
        />
        <action
          v-if="isEpub"
          icon="add"
          :label="$t('buttons.increaseFontSize')"
          @action="increaseFontSize"
        />
        <action
          :disabled="loading"
          v-if="perms?.modify && !isInShareContext"
          icon="mode_edit"
          :label="$t('buttons.rename')"
          @action="rename()"
        />
        <action
          :disabled="loading"
          v-if="perms?.delete && !isInShareContext"
          icon="delete"
          :label="$t('buttons.moveToTrash')"
          @action="moveToTrash"
          id="delete-button"
        />
        <action
          :disabled="loading"
          v-if="perms?.download"
          icon="file_download"
          :label="$t('buttons.download')"
          @action="download"
        />
        <action
          :disabled="loading"
          icon="info"
          :label="$t('buttons.info')"
          show="info"
        />
      </template>
    </header-bar>

    <div class="loading delayed" v-if="loading">
      <div class="spinner">
        <div class="bounce1"></div>
        <div class="bounce2"></div>
        <div class="bounce3"></div>
      </div>
    </div>
    <template v-else>
      <div class="preview">
        <div v-if="isEpub" class="epub-reader">

          <vue-reader
            :epubInitOptions="{ openAs: 'epub'}"
            :location="bookLocation"
            @update:location="locationChange"
            :url="fileSrcUrl"
            :getRendition="getRendition"
            :tocChanged="tocChanged">

          </vue-reader>
          <div class="page">
            {{ page }}
          </div>

        </div>

        <ExtendedImage v-else-if="file.type === 'image' && file.size > 0" :src="fileSrcUrl"/>
        <audio
          v-else-if="file.type === 'audio' && file.size > 0"
          ref="player"
          :src="fileSrcUrl"
          controls
          :autoplay="autoPlay"
          @play="autoPlay = true"
        ></audio>
        <video
          v-else-if="file.type === 'video' && file.size > 0"
          ref="video"
          controls
          :src="fileSrcUrl"
          :autoplay="autoPlay"
          @play="autoPlay = true"
        >
        </video>
        <object
          v-else-if="file.extension === '.pdf' && file.size > 0"
          class="pdf"
          :data="fileSrcUrl"
        ></object>
        <div v-else class="info">
          <div class="title">
            <i class="material-icons">feedback</i>
            {{ $t("files.noPreview") }}
          </div>
          <div>
            <a target="_blank" :href="file.download_url" class="button button--flat" download>
              <div>
                <i class="material-icons">file_download</i
                >{{ $t("buttons.download") }}
              </div>
            </a>
            <a
              target="_blank"
              :href="fileSrcUrl"
              class="button button--flat"
              v-if="!file.isDir"
            >
              <div>
                <i class="material-icons">open_in_new</i
                >{{ $t("buttons.openFile") }}
              </div>
            </a>
          </div>
        </div>
      </div>
    </template>

    <button
      @click="prev"
      @mouseover="hoverNav = true"
      @mouseleave="hoverNav = false"
      :class="{ hidden: !hasPrevious || !showNav }"
      :aria-label="$t('buttons.previous')"
      :title="$t('buttons.previous')"
    >
      <i class="material-icons">chevron_left</i>
    </button>
    <button
      @click="next"
      @mouseover="hoverNav = true"
      @mouseleave="hoverNav = false"
      :class="{ hidden: !hasNext || !showNav }"
      :aria-label="$t('buttons.next')"
      :title="$t('buttons.next')"
    >
      <i class="material-icons">chevron_right</i>
    </button>
  </div>
</template>

<script>
import {mapGetters, mapMutations, mapState} from "vuex"
import throttle from "lodash.throttle"
import HeaderBar from "@/components/header/HeaderBar.vue"
import Action from "@/components/header/Action.vue"
import ExtendedImage from "@/components/files/ExtendedImage.vue"
import {getFile} from "@/api/files.js"
import {getItems} from "@/api/folder.js"
import {getShare} from "@/api/share.js"
import {VueReader} from "vue-reader"
import {sortItems} from "@/utils/common.js";

export default {
   name: "preview",
   components: {
      HeaderBar,
      VueReader,
      Action,
      ExtendedImage,
   },

   props: {
      fileId: {
         type: String,
         required: true,
      },
      token: {
         type: String,
      },
      folderId: {
         type: String,
      },
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


      }
   },
   computed: {
      ...mapState(["items", "user", "selected", "loading", "perms", "currentFolder"]),
      ...mapGetters(["currentPrompt", "isLogged"]),
      isEpub() {
         if (!this.file) return false
         return this.file.extension === ".epub"
      },
      isInShareContext() {
         return this.token !== undefined
      },

      fileSrcUrl() {
         if (this.file.preview_url)
            return this.file.preview_url + "?inline=True"
         return this.file.download_url + "?inline=True"
      },

      currentIndex() {
         if (this.files && this.file) {
            return this.files.findIndex(item => item.id === this.file.id)
         }
      },

      files() {
         let files = []

         if (this.items != null) {
            this.items.forEach((item) => {
               if (!item.isDir && item.type !== "text" && item.type !== "application") {
                  files.push(item)
               }
            })
         }
         //return items
         return sortItems(files)
      },
      hasNext() {
         return this.currentIndex < this.files.length - 1 // list starts at 0 lul

      },
      hasPrevious() {

         return this.files.length > 1 && this.currentIndex > 0
      },

   },
   watch: {
      $route: function () {
         this.fetchData()
         this.toggleNavigation()
      },
   },
   created() {
      if (!this.isLogged) {
         this.$store.commit("setAnonState")

      }
      this.fetchData()

   },
   async mounted() {

      window.addEventListener("keydown", this.key)

   },
   beforeDestroy() {
      window.removeEventListener("keydown", this.key)
   },
   methods: {
      ...mapMutations(["setLoading"]),

      async fetchData() {

         this.setLoading(true)

         // Ensure loadingImage state is updated in the DOM
         this.file = null
         this.$nextTick(() => {
            if (this.items) {
               for (let i = 0; i < this.items.length; i++) {
                  if (this.items[i].id === this.fileId) {
                     this.file = this.items[i]

                  }
               }
            }
         })
         //only if file is null:
         if (!this.file) {

            if (this.isInShareContext) {

               let res = await getShare(this.token, this.folderId)
               this.shareObj = res

               this.$store.commit("setItems", res.share)
               this.folderList = res.breadcrumbs

               for (let i = 0; i < this.items.length; i++) {
                  if (this.items[i].id === this.fileId) {
                     this.file = this.items[i]
                  }
               }

            } else {

               this.file = await getFile(this.fileId, this.lockFrom)
               if (!this.currentFolder) {
                  const res = await getItems(this.file.parent_id, this.file.lockFrom)

                  this.$store.commit("setItems", res.folder.children)
                  this.$store.commit("setCurrentFolder", res.folder)
               }

            }
         }
         this.$store.commit("addSelected", this.file)
         this.setLoading(false)
         if (!this.isEpub) return
         this.bookLocation = localStorage.getItem('book-progress-' + this.file.id)
         let fontsize = localStorage.getItem('font-size')
         this.fontSize = (fontsize < 600) ? fontsize : 100


      },
      moveToTrash() {
         this.$store.commit("showHover", {
            prompt: "moveToTrash",
            confirm: () => {
               this.close()
            },
         })

      },
      rename() {
         this.$store.commit("showHover", "rename")

      },
      prev() {
         this.hoverNav = false
         if (this.hasPrevious) {
            let previousFile = this.files[this.currentIndex - 1]
            if (this.isInShareContext) {
               this.$router.push({
                  name: "SharePreview",
                  params: {"folderId": previousFile.parent_id, "fileId": previousFile.id, "token": this.token}
               })

            } else {
               this.$router.push({
                  name: "Preview",
                  params: {"fileId": previousFile.id, "lockFrom": previousFile.lockFrom}
               })

            }
         }

      },
      next() {
         this.hoverNav = false
         if (this.hasNext) {
            let nextFile = this.files[this.currentIndex + 1]
            if (this.isInShareContext) {
               this.$router.push({
                  name: "SharePreview",
                  params: {"folderId": nextFile.parent_id, "fileId": nextFile.id, "token": this.token}
               })

            } else {
               this.$router.push({name: "Preview", params: {"fileId": nextFile.id, "lockFrom": nextFile.lockFrom}})

            }
         }
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
         this.$store.commit("closeHover")
      },
      toggleNavigation: throttle(function () {
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


         let parent_id = this.file?.parent_id

         if (this.isInShareContext) {
            this.$router.push({name: "Share", params: {"token": this.token, "folderId": this.folderId}})
            return
         }
         if (parent_id) {
            //this.$store.commit("updateItems", {})
            this.$router.push({name: `Files`, params: {"folderId": parent_id}})

         } else {
            this.$router.push({name: `Files`, params: {folderId: this.$store.state.user.root}})


         }
      },
      download() {
         window.open(this.selected[0].download_url, '_blank')
         let message = this.$t("toasts.downloadingSingle", {name: this.selected[0].name})
         this.$toast.success(message)
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
                  'font-size': `${this.fontSize}%`,


               },
            });
            this.rendition.flow('paginated'); // For continuous scrolling

         }
      },
      increaseFontSize() {
         if (this.fontSize < 500) {
            this.fontSize += 20
            localStorage.setItem('font-size', this.fontSize)
            this.applyStyles()
         }
      },
      calcCurrentLocation() {
         let {displayed} = this.rendition.location.start
         let percentage = Math.round(displayed.page / displayed.total * 100)
         this.page = `${percentage}% finished • ${displayed.total - displayed.page} pages left in this chapter`

      },

      decreaseFontSize() {
         if (this.fontSize > 60) {
            this.fontSize -= 20
            localStorage.setItem('font-size', this.fontSize)
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
         //   let container = this.rendition.manager.container;
         //   console.log(container)
         //   let iframe = container.querySelector('iframe');
         //   console.log(iframe)
         //
         //   if (iframe) {
         //     const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
         //     console.log(iframeDocument)
         //     const body = iframeDocument.querySelector('body');
         //
         //     if (body) {
         //       // Modify body styles directly
         //       body.style.setProperty('padding-left', '30px', 'important');
         //       body.style.setProperty('padding-right', '30px', 'important');
         //       body.style.setProperty('padding-top', '20px', 'important');
         //       body.style.setProperty('padding-bottom', '20px', 'important');
         //     }
         //   }
         // }

         // let container = this.rendition.manager.container;
         // console.log(container)
         // let iframe = container.querySelector('iframe');
         // console.log(iframe)
         //
         // if (iframe) {
         //   const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
         //   console.log(iframeDocument)
         //
         //   iframeDocument.addEventListener('scroll', (event) => {
         //     const scrollDirection = event.deltaX < 0 ? 'left' : 'right';
         //     // Handle the scroll direction and adjust navigation accordingly
         //     console.log(`Scrolled ${scrollDirection}`);
         //   });
         // }

         localStorage.setItem('book-progress-' + this.file.id, epubcifi)
         this.bookLocation = epubcifi
      },
   },
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
</style>