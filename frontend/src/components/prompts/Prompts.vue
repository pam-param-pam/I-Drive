<template>
   <div>
      <component
         :is="prompt.prompt"
         v-for="(prompt, index) in prompts"
         v-show="prompt.prompt === currentPromptName"
         :key="index"
         :ref="prompt.prompt"
         v-bind="prompt.props"
      />

      <div v-show="showOverlay" class="overlay" @click="resetPrompts"></div>
      <div v-show="!showOverlay" @click="resetPrompts"></div>
   </div>
</template>

<script>
import Help from './Help.vue'
import Info from './Info.vue'
import Delete from './Delete.vue'
import Rename from './Rename.vue'
import Move from './Move.vue'
import NewDir from './NewDir.vue'
import DiscardEditorChanges from './DiscardEditorChanges.vue'
import Share from './Share.vue'
import Upload from './Upload.vue'
import ShareDelete from './ShareDelete.vue'
import FolderPassword from '@/components/prompts/FolderPassword.vue'
import EditFolderPassword from '@/components/prompts/EditFolderPassword.vue'
import MoveToTrash from '@/components/prompts/MoveToTrash.vue'
import RestoreFromTrash from '@/components/prompts/RestoreFromTrash.vue'
import SearchTunePrompt from '@/components/prompts/SearchTunePrompt.vue'
import NotOptimizedForSmallFiles from '@/components/prompts/NotOptimizedForSmallFiles.vue'
import ResetFolderPassword from '@/components/prompts/ResetFolderPassword.vue'
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'
import Sidebar from '@/components/sidebar/Sidebar.vue'
import EditTags from '@/components/prompts/EditTags.vue'
import UploadDestinationWarning from '@/components/prompts/UploadDestinationWarning.vue'
import EditThumbnail from '@/components/prompts/EditThumbnail.vue'

export default {
   name: 'prompts',

   components: {
      Info,
      Delete,
      MoveToTrash,
      RestoreFromTrash,
      Rename,
      Move,
      Share,
      NewDir,
      Help,
      Upload,
      ShareDelete,
      Sidebar,
      DiscardEditorChanges,
      FolderPassword,
      EditFolderPassword,
      SearchTunePrompt,
      NotOptimizedForSmallFiles,
      ResetFolderPassword,
      EditTags,
      UploadDestinationWarning,
      EditThumbnail
   },

   created() {
      window.addEventListener('keydown', (event) => {
         if (this.currentPrompt == null) return

         // Esc!
         if (event.code === 'Escape') {
            event.stopImmediatePropagation()
            this.resetPrompts()
         }
         // Enter!
         if (event.code === 'Enter') {
            event.preventDefault()

            let promptComponent = this.$refs[this.currentPromptName][0]
            if (promptComponent && typeof promptComponent.submit === 'function') {
               promptComponent.submit()
            } else {
               console.warn("couldn't find submit method for prompt:")
               console.warn(this.currentPromptName)
            }
         }
      })
   },

   computed: {
      ...mapState(useMainStore, ['currentPrompt', 'currentPromptName', 'prompts']),
      showOverlay() {
         return this.currentPrompt !== null && this.currentPromptName !== 'more'
      }
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover']),

      resetPrompts() {
         let promptComponent = this.$refs[this.currentPromptName][0]
         if (promptComponent && typeof promptComponent.cancel === 'function') {
            promptComponent.cancel()
         } else {
            console.warn("couldn't find cancel method for prompt:")
            console.warn(this.currentPromptName)
            this.closeHover()
         }
      }
   }
}
</script>
