<template>

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
</template>

<script>
import Prompts from '@/components/prompts/Prompts.vue'
import Shell from '@/components/Shell.vue'
import UploadFiles from '../components/prompts/UploadFiles.vue'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { useUploadStore } from '@/stores/uploadStore.js'
import Sidebar from '@/components/sidebar/Sidebar.vue'

export default {
   name: 'layout',

   components: {
      Sidebar,
      Prompts,
      Shell,
      UploadFiles
   },

   created() {
      if (!this.isLogged) {
         this.setAnonState()
      }
   },

   computed: {
      ...mapState(useMainStore, ['perms', 'isLogged']),
      ...mapState(useUploadStore, ['progress']),

      isExecEnabled() {
         return this.perms?.execute
      }
   },

   methods: {
      ...mapActions(useMainStore, ['setAnonState'])
   }
}
</script>
