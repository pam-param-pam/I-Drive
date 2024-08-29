<template>
  <div>
    <component
      v-if="showOverlay"
      :ref="currentPromptName"
      :is="currentPromptName"
      v-bind="currentPrompt.props"
    >
    </component>
    <div v-show="showOverlay" @click="resetPrompts" class="overlay"></div>
    <div v-show="!showOverlay" @click="resetPrompts"></div>
  </div>
</template>

<script>
import Help from "./Help.vue"
import Info from "./Info.vue"
import Delete from "./Delete.vue"
import Rename from "./Rename.vue"
import Move from "./Move.vue"
import NewFile from "./NewFile.vue"
import NewDir from "./NewDir.vue"
import DiscardEditorChanges from "./DiscardEditorChanges.vue"
import Share from "./Share.vue"
import Upload from "./Upload.vue"
import ShareDelete from "./ShareDelete.vue"
import Sidebar from "../Sidebar.vue"
import FolderPassword from "@/components/prompts/FolderPassword.vue"
import EditFolderPassword from "@/components/prompts/EditFolderPassword.vue"
import MoveToTrash from "@/components/prompts/MoveToTrash.vue"
import RestoreFromTrash from "@/components/prompts/RestoreFromTrash.vue"
import SearchTunePrompt from "@/components/prompts/SearchTunePrompt.vue"
import NotOptimizedForSmallFiles from "@/components/prompts/NotOptimizedForSmallFiles.vue"
import ResetFolderPassword from "@/components/prompts/ResetFolderPassword.vue"
import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"

export default {
   name: "prompts",
   components: {
      Info,
      Delete,
      MoveToTrash,
      RestoreFromTrash,
      Rename,
      Move,
      Share,
      NewFile,
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
   },
   created() {

      window.addEventListener("keydown", (event) => {
         if (this.currentPrompt == null) return

         // Esc!
         if (event.code === "Escape") {
            event.stopImmediatePropagation()
            this.resetPrompts()
         }
         // Enter!
         if (event.code === "Enter") {
            event.preventDefault()

            let promptComponent = this.$refs[this.currentPromptName]
            if (promptComponent && typeof promptComponent.submit === 'function') {
               promptComponent.submit()
            } else {
               console.warn("couldn't find submit method for prompt:")
               console.warn(this.currentPromptName)
               this.closeHover()
            }
         }
      })
   },

   computed: {
      ...mapState(useMainStore, ["currentPrompt", "currentPromptName"]),
      showOverlay() {
         return this.currentPrompt !== null && this.currentPromptName !== "more"
      },
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      resetPrompts() {
         let promptComponent = this.$refs[this.currentPromptName]
         if (promptComponent && typeof promptComponent.cancel === 'function') {
            promptComponent.cancel()
         } else {
            console.warn("couldn't find cancel method for prompt:")
            console.warn(this.currentPromptName)
            this.closeHover()

         }
      },

   },
}
</script>
