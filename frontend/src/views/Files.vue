<template>
  <div>
    <header-bar v-if="error" showMenu showLogo/>

    <breadcrumbs base="/files"/>

    <errors v-if="error" :errorCode="error.status"/>
    <component v-else-if="currentView" :is="currentView"></component>
    <div v-else>
      <h2 class="message delayed">
        <div class="spinner">
          <div class="bounce1"></div>
          <div class="bounce2"></div>
          <div class="bounce3"></div>
        </div>
        <span>{{ $t("files.loading") }}</span>
      </h2>
    </div>
  </div>
</template>

<script>
import {mapState, mapMutations} from "vuex";

import HeaderBar from "@/components/header/HeaderBar.vue";
import Breadcrumbs from "@/components/Breadcrumbs.vue";
import Errors from "@/views/Errors.vue";
import Preview from "@/views/files/Preview.vue";
import Listing from "@/views/files/Listing.vue";
import {getItems} from "@/api/folder.js";

export default {
  name: "files",
  components: {
    HeaderBar,
    Breadcrumbs,
    Errors,
    Preview,
    Listing,
    Editor: () => import("@/views/files/Editor.vue"),
  },
  data: function () {
    return {
      error: null,
      width: window.innerWidth,
    };
  },
  computed: {
    ...mapState(["reload", "loading"]),
    currentView() {
      if (this.$router.currentRoute.path.includes("preview")) {
        return "preview";

      } else if (this.$router.currentRoute.path.includes("editor")) {
        return "editor";

      }

      return "listing"
    },
  },
  created() {
    this.fetchData();
  },
  watch: {
    $route: "fetchData",
    reload: function (value) {
      if (value === true) {
        this.fetchData();
      }
    },
  },
  mounted() {
    window.addEventListener("keydown", this.keyEvent);
  },
  beforeDestroy() {
    window.removeEventListener("keydown", this.keyEvent);
  },
  destroyed() {
    this.$store.commit("setItems", null);
    this.$store.commit("setCurrentFolder", null);

  },
  methods: {
    ...mapMutations(["setLoading"]),
    async fetchData() {
      // Reset view information.
      this.$store.commit("setReload", false);
      this.$store.commit("resetSelected");
      this.$store.commit("closeHovers");

      // Set loading to true and reset the error.
      this.setLoading(true);
      this.error = null;

      let url = this.$route.path;
      try {
        this.$store.commit("setReload", false);

        const res = await getItems(url);

        this.$store.commit("setItems", res.children);
        this.$store.commit("setCurrentFolder", res);

        document.title = `${res.name} - File Browser`;
      } catch (e) {
        this.error = e;
      } finally {
        this.setLoading(false);

      }
    },
    keyEvent(event) {
      // H!
      if (event.keyCode === 72) {
        event.preventDefault();
        this.$store.commit("showHover", "help");
      }
    },
  },
};
</script>
