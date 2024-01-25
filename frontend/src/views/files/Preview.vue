<template>
  <div
    id="previewer"
    @mousemove="toggleNavigation"
    @touchstart="toggleNavigation"
  >
    <header-bar>
      <action icon="close" :label="$t('buttons.close')" @action="close()" />
      <title>{{ name }}</title>
      <action
        :disabled="loading"
        v-if="isResizeEnabled && item.extension === '.jpg'"
        :icon="fullSize ? 'photo_size_select_large' : 'hd'"
        @action="toggleSize"
      />

      <template #actions>
        <action
          :disabled="loading"
          v-if="perms.rename"
          icon="mode_edit"
          :label="$t('buttons.rename')"
          show="rename"
        />
        <action
          :disabled="loading"
          v-if="perms.delete"
          icon="delete"
          :label="$t('buttons.delete')"
          @action="deleteFile"
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
        <ExtendedImage v-if="this.item.extension === '.jpg'" :src="raw"></ExtendedImage>
        <audio
          v-else-if="item.extension === '.mp3'"
          ref="player"
          :src="raw"
          controls
          :autoplay="autoPlay"
          @play="autoPlay = true"
        ></audio>
        <video
          v-else-if="item.extension === '.mp4'"
          ref="video"
          controls
          :autoplay="autoPlay"
          @play="autoPlay = true"
        >
        </video>
        <object
          v-else-if="item.extension === '.pdf'"
          class="pdf"
          :data="raw"
        ></object>
        <div v-else class="info">
          <div class="title">
            <i class="material-icons">feedback</i>
            {{ $t("files.noPreview") }}
          </div>
          <div>
            <a target="_blank" :href="downloadUrl" class="button button--flat">
              <div>
                <i class="material-icons">file_download</i
                >{{ $t("buttons.download") }}
              </div>
            </a>
            <a
              target="_blank"
              :href="raw"
              class="button button--flat"
              v-if="!req.isDir"
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
    <link rel="prefetch" :href="previousRaw" />
    <link rel="prefetch" :href="nextRaw" />
  </div>
</template>

<script>
import { mapGetters, mapState } from "vuex";
import { files as api } from "@/api";
import {baseURL, resizePreview} from "@/utils/constants";
import Hls from 'hls.js';
import throttle from "lodash.throttle";
import HeaderBar from "@/components/header/HeaderBar.vue";
import Action from "@/components/header/Action.vue";
import ExtendedImage from "@/components/files/ExtendedImage.vue";
import store from "@/store/index.js";
import {getFile} from "@/api/files.js";

const mediaTypes = ["image", "video", "audio", "blob"];

export default {
  name: "preview",
  components: {
    HeaderBar,
    Action,
    ExtendedImage,
  },
  data: function () {
    return {
      previousLink: "",
      nextLink: "",
      listing: null,
      name: "",
      fullSize: false,
      showNav: true,
      file: null,
      navTimeout: null,
      hoverNav: false,
      autoPlay: false,
      previousRaw: "",
      nextRaw: "",
    };
  },
  computed: {
    ...mapState(["items", "user", "selected", "loading", "settings", "perms", "currentFolder"]),
    ...mapGetters(["currentPrompt"]),
    hasPrevious() {
      return this.previousLink !== "";
    },

    hasNext() {
      return this.nextLink !== "";
    },
    downloadUrl() {
      return ""
      return api.getDownloadURL(this.req);
    },
    raw() {
      /*
      if (this.req.type === "image" && !this.fullSize) {
        return api.getPreviewURL(this.req, "big");
      }

      return api.getDownloadURL(this.req, true);

       */
    },
    showMore() {
      return this.currentPrompt?.prompt === "more";
    },
    isResizeEnabled() {
      return resizePreview;
    },

  },
  watch: {
    $route: function () {
      this.updatePreview();
      this.toggleNavigation();
    },
  },
  created() {
    this.fetchData()
  },
  async mounted() {


    let hls = new Hls({

      xhrSetup: xhr => {
        xhr.setRequestHeader('Authorization', `Token ${store.state.token}`)
        xhr.setRequestHeader('Origin', `https://discord.com/`)
        xhr.setRequestHeader('Referer', `https://discord.com/`)

      }
    })

    let stream = baseURL +  `/api/stream/${item_id}`
    let video = this.$refs["video"];
    hls.loadSource(stream);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, function () {
      video.play();
    });


    window.addEventListener("keydown", this.key);
    this.listing = this.items;
    this.updatePreview();
  },
  beforeDestroy() {
    window.removeEventListener("keydown", this.key);
  },
  methods: {
    fetchData() {
      let fileId = this.$route.params.fileId;

      this.setLoading(true);

      try {

        if (this.items) {
          console.log(JSON.stringify(this.items))
        }
        else {
          console.log(JSON.stringify(this.items))
        }



      } catch (e) {
        console.log(e)
        this.error = e;
      } finally {
        this.setLoading(false);

      }
    },
    deleteFile() {
      this.$store.commit("showHover", {
        prompt: "delete",
        confirm: () => {
          this.listing = this.listing.filter((item) => item.name !== this.name);

          if (this.hasNext) {
            this.next();
          } else if (!this.hasPrevious && !this.hasNext) {
            this.close();
          } else {
            this.prev();
          }
        },
      });
    },
    prev() {
      this.hoverNav = false;
      this.$router.replace({ path: this.previousLink });
    },
    next() {
      this.hoverNav = false;
      this.$router.replace({ path: this.nextLink });
    },
    key(event) {
      if (this.currentPrompt !== null) {
        return;
      }

      if (event.which === 13 || event.which === 39) {
        // right arrow
        if (this.hasNext) this.next();
      } else if (event.which === 37) {
        // left arrow
        if (this.hasPrevious) this.prev();
      } else if (event.which === 27) {
        // esc
        this.close();
      }
    },
    async updatePreview() {
      /*
      if (
        this.$refs.player &&
        this.$refs.player.paused &&
        !this.$refs.player.ended
      ) {
        this.autoPlay = false;
      }

      let dirs = this.$route.fullPath.split("/");
      this.name = decodeURIComponent(dirs[dirs.length - 1]);

      if (!this.listing) {
        try {
          const path = url.removeLastDir(this.$route.path);
          const res = await api.getItems(path);
          this.listing = res.items;
        } catch (e) {
          this.$showError(e);
        }
      }

      this.previousLink = "";
      this.nextLink = "";

      for (let i = 0; i < this.listing.length; i++) {
        if (this.listing[i].name !== this.name) {
          continue;
        }

        for (let j = i - 1; j >= 0; j--) {
          if (mediaTypes.includes(this.listing[j].type)) {
            this.previousLink = this.listing[j].url;
            this.previousRaw = this.prefetchUrl(this.listing[j]);
            break;
          }
        }
        for (let j = i + 1; j < this.listing.length; j++) {
          if (mediaTypes.includes(this.listing[j].type)) {
            this.nextLink = this.listing[j].url;
            this.nextRaw = this.prefetchUrl(this.listing[j]);
            break;
          }
        }

        return;
      }

       */
    },
    prefetchUrl(item) {
      if (item.type !== "image") {
        return "";
      }

      return this.fullSize
        ? api.getDownloadURL(item, true)
        : api.getPreviewURL(item, "big");
    },
    openMore() {
      this.$store.commit("showHover", "more");
    },
    resetPrompts() {
      this.$store.commit("closeHovers");
    },
    toggleSize() {
      this.fullSize = !this.fullSize;
    },
    toggleNavigation: throttle(function () {
      this.showNav = true;

      if (this.navTimeout) {
        clearTimeout(this.navTimeout);
      }

      this.navTimeout = setTimeout(() => {
        this.showNav = false || this.hoverNav;
        this.navTimeout = null;
      }, 1500);
    }, 500),
    close() {
      this.$store.commit("updateItems", {});
      let uri = `/files/folder/${this.currentFolder.id}`

      this.$router.push({ path: uri });
    },
    download() {
      window.open(this.downloadUrl);
    },
  },
};
</script>
