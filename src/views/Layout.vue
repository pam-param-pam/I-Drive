<template>
  <div>
    <div v-if="progress" class="progress">
      <div v-bind:style="{ width: this.progress + '%' }"></div>
    </div>
    <sidebar></sidebar>
    <main>
      <router-view></router-view>
      <shell v-if="isExecEnabled"></shell>
    </main>
    <upload-files></upload-files>
    <prompts></prompts>
  </div>
</template>

<script>
import Sidebar from "@/components/Sidebar.vue"
import Prompts from "@/components/prompts/Prompts.vue"
import Shell from "@/components/Shell.vue"
import UploadFiles from "../components/prompts/UploadFiles.vue"
import {useMainStore} from "@/stores/mainStore.js"
import {mapState} from "pinia"
import {useUploadStore} from "@/stores/uploadStore.js";

export default {
   name: "layout",
   components: {
      Sidebar,
      Prompts,
      Shell,
      UploadFiles,
   },

   renderTriggered({key, target, type}) {
      console.log(`Render triggered on component 'Layout'`, {key, target, type})
   },
   computed: {
      ...mapState(useMainStore, ["perms"]),
      ...mapState(useUploadStore, ["progress"]),

      isExecEnabled() {
         return this.perms?.execute
      }
   },
}
</script>
