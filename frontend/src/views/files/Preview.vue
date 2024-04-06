<template>
  <div
    id="previewer"
    @mousemove="toggleNavigation"
    @touchstart="toggleNavigation"
  >
    <header-bar>
      <action icon="close" :label="$t('buttons.close')" @action="close()"/>
      <title v-if="file">{{ file.name }}</title>
      <template #actions>
        <action
          :disabled="loading"
          v-if="perms.rename"
          icon="mode_edit"
          :label="$t('buttons.rename')"
          @action="rename()"
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
        <ExtendedImage v-if="file.type === 'image'" :src="file.preview_url"></ExtendedImage>
        <audio
          v-else-if="file.type === 'audio'"
          ref="player"
          :src="file.preview_url"
          controls
          :autoplay="autoPlay"
          @play="autoPlay = true"
        ></audio>
        <video
          v-else-if="file.type === 'video'"
          ref="video"
          controls
          :src="file.preview_url"
          :autoplay="autoPlay"
          @play="autoPlay = true"
        >
        </video>
        <object
          v-else-if="file.extension === '.pdf'"
          class="pdf"
          :data="file.preview_url"
        ></object>
        <div v-else class="info">
          <div class="title">
            <i class="material-icons">feedback</i>
            {{ $t("files.noPreview") }}
          </div>
          <div>
            <a target="_blank" :href="file.preview_url" class="button button--flat" download>
              <div>
                <i class="material-icons">file_download</i
                >{{ $t("buttons.download") }}
              </div>
            </a>
            <a
              target="_blank"
              :href="file.preview_url"
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
import {mapGetters, mapMutations, mapState} from "vuex";
import throttle from "lodash.throttle";
import HeaderBar from "@/components/header/HeaderBar.vue";
import Action from "@/components/header/Action.vue";
import ExtendedImage from "@/components/files/ExtendedImage.vue";
import {getFile} from "@/api/files.js";
import {getItems} from "@/api/folder.js";
import {sortItems} from "@/api/utils.js";

export default {
  name: "preview",
  components: {
    HeaderBar,
    Action,
    ExtendedImage,
  },
  data: function () {
    return {
      fullSize: false,
      showNav: true,
      file: null,
      navTimeout: null,
      hoverNav: false,
      autoPlay: true,
    };
  },
  computed: {
    ...mapState(["items", "user", "selected", "loading", "settings", "perms", "currentFolder"]),
    ...mapGetters(["currentPrompt"]),
    currentIndex() {
      if (this.files && this.file) {
        return this.files.findIndex(item => item.id === this.file.id);
      }
    },
    files() {
      const items = [];

      if (this.items != null) {
        this.items.forEach((item) => {
          if (!item.isDir) {
            items.push(item);
          }
        });
      }

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
      this.fetchData();
      this.toggleNavigation();
    },
  },
  created() {
    this.fetchData()
  },
  async mounted() {

    window.addEventListener("keydown", this.key);

  },
  beforeDestroy() {
    window.removeEventListener("keydown", this.key);
  },
  methods: {
    ...mapMutations(["setLoading"]),

    async fetchData() {

      let fileId = this.$route.params.fileId;

      this.setLoading(true);

      try {
        this.file = await getFile(fileId)
        if (!this.currentFolder) {
          const res = await getItems(this.file.parent_id);

          this.$store.commit("setItems", res.children);
          this.$store.commit("setCurrentFolder", res);

        }
        this.$store.commit("addSelected", this.file);

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
          this.close()
        },
      });

    },
    rename() {
      this.$store.commit("showHover", {
        prompt: "rename",
        confirm: (newName) => {
          this.file.name = newName
        },
      });

    },
    prev() {
      this.hoverNav = false;
      if (this.hasPrevious) {
        let previousFile = this.files[this.currentIndex - 1];
        this.$router.replace({path: previousFile.id});
      }

    },
    next() {
      this.hoverNav = false;
      if (this.hasNext) {
        let nextFile = this.files[this.currentIndex + 1];
        this.$router.replace({path: nextFile.id});
      }
    },
    key(event) {

      if (this.currentPrompt !== null) {
        return;
      }

      if (event.which === 13 || event.which === 39) {
        // right arrow
        this.next();
      } else if (event.which === 37) {
        // left arrow
        this.prev();
      } else if (event.which === 27) {
        // esc
        this.close();
      }
    },


    resetPrompts() {
      this.$store.commit("closeHover");
    },
    toggleNavigation: throttle(function () {
      this.showNav = true;

      if (this.navTimeout) {
        clearTimeout(this.navTimeout);
      }

      this.navTimeout = setTimeout(() => {
        this.showNav = this.hoverNav;
        this.navTimeout = null;
      }, 1500);
    }, 500),
    close() {
      let parent_id = this.file?.parent_id
      if (parent_id) {
        this.$store.commit("updateItems", {});
        this.$router.push({path: `/folder/${parent_id}`});
      }
      else {
        this.$router.push("/files/");

      }
    },
    download() {
      //window.open(this.file.preview_url, '_blank');
    },
  },
};
</script>
