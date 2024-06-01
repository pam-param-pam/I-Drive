<template>
  <div
    id="previewer"
    @mousemove="toggleNavigation"
    @touchstart="toggleNavigation"
  >
    <header-bar>
      <action icon="close" :label="$t('buttons.close')" @action="close()"/>
      <title v-if="file">{{ file.name }}</title>
      <title v-else> </title>

      <template #actions>
        <action
          :disabled="loading"
          v-if="perms.modify"
          icon="mode_edit"
          :label="$t('buttons.rename')"
          @action="rename()"
        />
        <action
          :disabled="loading"
          v-if="perms.delete"
          icon="delete"
          :label="$t('buttons.moveToTrash')"
          @action="moveToTrash"
          id="delete-button"
        />
        <action
          :disabled="loading"
          v-if="perms.download"
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
        <ExtendedImage v-if="file.type === 'image' &&!loadingImage && file.size > 0" :src="fileSrcUrl"></ExtendedImage>
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
              :href="fileSrcUrl + '?inline=True'"
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
import {sortItems} from "@/api/utils.js"

export default {
  name: "preview",
  components: {
    HeaderBar,
    Action,
    ExtendedImage,
  },

  props: {
    fileId: String,
    token: String,
    isShare: Boolean,
  },

  data: function () {
    return {
      fullSize: false,
      showNav: true,
      file: null,
      navTimeout: null,
      hoverNav: false,
      autoPlay: true,
      loadingImage: false,

    }
  },
  computed: {
    ...mapState(["items", "user", "selected", "loading", "settings", "perms", "currentFolder"]),
    ...mapGetters(["currentPrompt"]),
    fileSrcUrl() {
      if (this.file.preview_url)
        return this.file.preview_url
      return this.file.download_url
    },

    currentIndex() {
      if (this.files && this.file) {
        return this.files.findIndex(item => item.id === this.file.id)
      }
    },
    files() {
      const items = []

      if (this.items != null) {
        this.items.forEach((item) => {
          if (!item.isDir && item.type !== "text" && item.type !== "application") {
            items.push(item)
          }
        })
      }
      //return items
      return sortItems(items)
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
      this.loadingImage = true

      this.file = null
      /*
      if (this.items) {
        for (let i = 0; i < this.items.length; i++) {
          if (this.items[i].id === fileId) {
            this.file = this.items[i]

          }
        }
      }
       */

      if (!this.file) {
        try {
          this.file = await getFile(this.fileId)
          if (!this.currentFolder && ! this.isShare) {
            const res = await getItems(this.file.parent_id)

            this.$store.commit("setItems", res.folder.children)
            this.$store.commit("setCurrentFolder", res.folder)

          }

        } catch (e) {
          console.log(e)
          this.error = e

        }
      }
      this.$store.commit("addSelected", this.file)

      this.setLoading(false)
      this.loadingImage = false
      console.log("loading false")

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
        console.log(previousFile)

        this.$router.push({name: "Preview", params: {"fileId": previousFile.id}} )
      }

    },
    next() {
      this.hoverNav = false
      if (this.hasNext) {
        let nextFile = this.files[this.currentIndex + 1]
        console.log(nextFile)
        this.$router.push({name: "Preview", params: {"fileId": nextFile.id}} )
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

      if (this.isShare) {
        console.log(this.token)
        this.$router.push({path: `/share/${this.token}`})
        return
      }
      if (parent_id) {
        //this.$store.commit("updateItems", {})
        this.$router.push({name: `Files`, params: {"folderId": parent_id}})

      }
      else {
        this.$router.push({name: `Files`, params: {folderId: this.$store.state.user.root}})


      }
    },
    download() {
      //window.open(this.file.preview_url, '_blank')
    },
  },
}
</script>
