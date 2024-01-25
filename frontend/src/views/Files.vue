<template>
  <div>
    <header-bar v-if="error" showMenu showLogo/>

    <breadcrumbs base="/files/"/>
    <errors v-if="error" :errorCode="error.status"/>

    <router-view></router-view>

  </div>
</template>

<script>
import {mapState, mapGetters} from "vuex";

import HeaderBar from "@/components/header/HeaderBar.vue";
import Breadcrumbs from "@/components/Breadcrumbs.vue";
import Errors from "@/views/Errors.vue";


export default {
  name: "files",
  components: {
    HeaderBar,
    Breadcrumbs,
    Errors,

    Editor: () => import("@/views/files/Editor.vue"),
  },
  data: function () {
    return {
      width: window.innerWidth,
    };
  },
  computed: {
    ...mapState(["user", "error"]),
    ...mapGetters(["currentPrompt"]),

  },
  created() {
    this.redirect();
  },
  watch: {
    $route: "redirect",
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
    async redirect() {

      let url = this.$route.path;

      if (url === "/files/" || url === "/files") {
        await this.$router.push({path: `/folder/${this.user.root}`});
      }

    },
    keyEvent(event) {
      // H!
      if (event.keyCode === 72) {
        if (this.currentPrompt !== null) {
          return;
        }
        event.preventDefault();

        if (this.prompts.length === 0) {
          this.$store.commit("showHover", "help");

        }
      }
    },
  },
};
</script>
