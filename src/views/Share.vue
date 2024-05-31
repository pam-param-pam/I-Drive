<template>
  <div>
    <header-bar v-if="error" showMenu showLogo />

    <errors v-if="error" :errorCode="error.status"/>
    <breadcrumbs v-if="!error"
                 :base="'/share/' + token"
                 :folderList="folderList"
    />

    <div>
      <header-bar showMenu="false" showLogo="false">


        <title/>
        <template #actions>

          <action
            :icon="viewIcon"
            :label="$t('buttons.switchView')"
            @action="switchView"
          />
          <action
            icon="file_download"
            :label="$t('buttons.download')"
            @action="download"
            :counter="selectedCount"
          />
          <action
            v-if="selectedCount > 0"
            icon="info"
            :disabled="!selectedCount > 0"
            :label="$t('buttons.info')"
            show="info"
          />


        </template>
      </header-bar>

      <div v-if="loading">
        <h2 class="message delayed">
          <div class="spinner">
            <div class="bounce1"></div>
            <div class="bounce2"></div>
            <div class="bounce3"></div>
          </div>
          <span>{{ $t("files.loading") }}</span>
        </h2>
      </div>


      <template v-else-if="error == null">

        <div v-if="dirsSize + filesSize === 0">
          <h2 class="message">
            <a href="https://www.youtube.com/watch?app=desktop&v=nGBYEUNKPmo">
              <img
                src="https://steamuserimages-a.akamaihd.net/ugc/2153341894595795931/DCCF2A0051A51653A133FB1A8123EA4D3696AB6C/?imw=637&imh=358&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=true"
                alt="You look lonely, I can fix that~">
            </a>
          </h2>
        </div>

        <div
          v-else
          id="listing"
          ref="listing"
          :class="viewMode + ' file-icons'"
          @dragenter.prevent @dragover.prevent
        >
          <div>

            <div class="item header normal-cursor">
              <div></div>
              <div>
                <p class="name">
                  <span>{{ $t("files.name") }}</span>
                </p>
                <p class="size">
                  <span>{{ $t("files.size") }}</span>
                </p>
                <p class="created">
                  <span>{{ $t("files.created") }}</span>
                </p>
              </div>
            </div>
          </div>

          <h2 v-if="dirsSize > 0">{{ $t("files.folders") }}</h2>
          <div v-if="dirsSize > 0">
            <item
              v-for="item in dirs"
              :key="item.id"
              :item="item"
              mode="share"
              @onOpen="onOpen"
              :readOnly="true"
              draggable="false"

            >
            </item>
          </div>

          <h2 v-if="filesSize > 0">{{ $t("files.files") }}</h2>
          <div v-if="filesSize > 0">

            <item
              v-for="item in files"
              :key="item.id"
              :item="item"
              :readOnly="true"
              mode="share"
              @onOpen="onOpen"
              draggable="false"

            ></item>

          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<script>
import {mapGetters, mapMutations, mapState} from "vuex";

import Breadcrumbs from "@/components/Breadcrumbs.vue";
import Errors from "@/views/Errors.vue";
import Listing from "@/views/files/Listing.vue";
import HeaderBar from "@/components/header/HeaderBar.vue";
import {getShare} from "@/api/share.js";
import Action from "@/components/header/Action.vue";
import Item from "@/components/files/ListingItem.vue";
import Vue from "vue";
import css from "@/utils/css.js";
import throttle from "lodash.throttle";

export default {
  name: "files",
  components: {
    Action,
    HeaderBar,
    Breadcrumbs,
    Errors,
    Listing,
    Item,
  },
  props: {
    token: String,
    folderId: String,

  },
  data: function () {
    return {
      items: [],
      folderList: [],
      viewMode: "mosaic",
      columnWidth: 280,
      width: window.innerWidth,
      itemWeight: 0,

    };
  },
  computed: {
    ...mapState(["reload", "selected", "loading", "error", "disableCreation"]),
    ...mapGetters(["selectedCount", "currentPrompt", "currentPromptName"]),

    dirs() {
      const items = [];
      if (this.items != null) {
        this.items.forEach((item) => {
          if (item.isDir) {
            items.push(item);
          }

        });
      }
      return items
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
      return items
    },
    dirsSize() {
      return this.dirs.length
    },
    filesSize() {
      return this.files.length
    },

    viewIcon() {
      const icons = {
        list: "view_module",
        mosaic: "grid_view",
        "mosaic gallery": "view_list",
      };
      return icons[this.viewMode];
    },

  },
  created() {
    this.setDisableCreation(true)

    this.fetchFolder()

  },

  watch: {
    $route: "fetchFolder",


  },
  mounted() {
    // Check the columns size for the first time.
    this.columnsResize();

    window.addEventListener("resize", this.windowsResize);

  },
  beforeDestroy() {
    window.removeEventListener("resize", this.windowsResize);

  },

  methods: {
    ...mapMutations(["addSelected", "setLoading", "setError", "setDisableCreation"]),


    switchView: async function () {
      this.$store.commit("closeHover");

      const modes = ["list", "mosaic", "mosaic gallery"];

      let currentIndex = modes.indexOf(this.viewMode);
      let nextIndex = (currentIndex + 1) % modes.length;
      this.viewMode = modes[nextIndex];


    },
    download() {

    },
    onOpen(item) {
      console.log("BBBBBB")

      if (item.isDir) {
        this.$router.push({name: "Share", params: {"token": this.token, "folderId": item.id}});

      }

    else {
        console.log("AAAAAA")
        if (item.type === "audio" || item.type === "video" || item.type === "image" ||  item.size >= 25 * 1024 * 1024 || item.extension === ".pdf") {
          this.$router.push({name: "Preview", params: {"fileId":item.id, "token": this.token, "isShare": true}} );

        }
        else {
          this.$router.push({name: "Editor", params: {"fileId": item.id, "token": this.token, "isShare": true}} );

        }
      }


    },
    async fetchFolder() {

      this.setLoading(true);
      this.setError(null)

      try {

        let res = await getShare(this.token, this.folderId)
        console.log(res)
        this.items = res.share

        this.folderList = res.breadcrumbs

        document.title = "share"


      } catch (error) {
        console.log(error)
        this.setError(error);


      } finally {
        this.setLoading(false);

      }

    },
    windowsResize: throttle(function () {
      this.columnsResize();
      this.width = window.innerWidth;

      // Listing element is not displayed
      if (this.$refs.listing == null) return;

      // How much every listing item affects the window height
      this.setItemWeight();

      // Fill but not fit the window
      this.fillWindow();
    }, 100),
    columnsResize() {
      // Update the columns size based on the window width.
      let items = css(["#listing.mosaic .item", ".mosaic#listing .item"]);
      if (!items) return;

      let columns = Math.floor(
        document.querySelector("main").offsetWidth / this.columnWidth
      );
      if (columns === 0) columns = 1;
      items.style.width = `calc(${100 / columns}% - 1em)`;
    },

  },
};
</script>
<style>
.normal-cursor {
   cursor: default !important;
}
</style>