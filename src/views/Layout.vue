<template>
  <div>
    <div v-if="progress" class="progress">
      <div v-bind:style="{ width: this.progress + '%' }"></div>
    </div>
    <sidebar></sidebar>
    <main>
      <router-view></router-view>
      <shell v-if="true"></shell>
      </main>
      <prompts></prompts>
      <upload-files></upload-files>
    </div>
  </template>

  <script>
  import { mapState, mapGetters } from "vuex"
  import Sidebar from "@/components/Sidebar.vue"
  import Prompts from "@/components/prompts/Prompts.vue"
  import Shell from "@/components/Shell.vue"
  import UploadFiles from "../components/prompts/UploadFiles.vue"
  import { enableExec } from "@/utils/constants"

  export default {
    name: "layout",
    components: {
      Sidebar,
      Prompts,
      Shell,
      UploadFiles,
    },
    computed: {
      ...mapGetters(["isLogged", "progress", "currentPrompt"]),
      ...mapState(["user", "perms"]),
      isExecEnabled: () => enableExec,
    },
    watch: {
      $route: function () {
        this.$store.commit("resetSelected")
        if (this.currentPrompt?.prompt !== "success")
          this.$store.commit("closeHover")
      },
    },
  }
  </script>
