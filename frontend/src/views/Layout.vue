<template>

   <div v-if="progress" class="progress">
      <div v-bind:style="{ width: this.progress + '%' }"></div>
   </div>
   <sidebar></sidebar>
   <main>
      <router-view></router-view>
   </main>

   <upload-files></upload-files>
   <prompts></prompts>
</template>

<script>
import Prompts from "@/components/prompts/Prompts.vue"
import UploadFiles from "../components/prompts/UploadFiles.vue"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { useUploadStore } from "@/stores/uploadStore.js"
import Sidebar from "@/components/sidebar/Sidebar.vue"

export default {
   name: "layout",

   components: {
      Sidebar,
      Prompts,
      UploadFiles
   },

   created() {
      if (!this.isLogged) {
         this.setAnonState()
      }
   },

   computed: {
      ...mapState(useMainStore, ["isLogged"]),
      ...mapState(useUploadStore, ["progress"])
   },

   methods: {
      ...mapActions(useMainStore, ["setAnonState"])
   }
}
</script>
