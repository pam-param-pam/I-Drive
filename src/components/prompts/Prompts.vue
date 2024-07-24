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
  </div>
</template>

<script>

import { mapGetters } from "vuex"


export default {
  name: "prompts",
  components: {
    // Import components dynamically
    // Note: You can add more components as needed
    Info: () => import("./Info.vue"),
    Delete: () => import("./Delete.vue"),
    MoveToTrash: () => import("@/components/prompts/MoveToTrash.vue"),
    RestoreFromTrash: () => import("@/components/prompts/RestoreFromTrash.vue"),
    Rename: () => import("./Rename.vue"),
    Move: () => import("./Move.vue"),
    Share: () => import("./Share.vue"),
    NewFile: () => import("./NewFile.vue"),
    NewDir: () => import("./NewDir.vue"),
    Help: () => import("./Help.vue"),
    Upload: () => import("./Upload.vue"),
    ShareDelete: () => import("./ShareDelete.vue"),
    Sidebar: () => import("../Sidebar.vue"),
    DiscardEditorChanges: () => import("./DiscardEditorChanges.vue"),
    FolderPassword: () => import("@/components/prompts/FolderPassword.vue"),
    EditFolderPassword: () => import("@/components/prompts/EditFolderPassword.vue"),
    SearchTunePrompt: () => import("@/components/prompts/SearchTunePrompt.vue"),
    NotOptimizedForSmallFiles: () => import("@/components/prompts/NotOptimizedForSmallFiles.vue"),
    ResetFolderPassword: () => import("@/components/prompts/ResetFolderPassword.vue"),
  },
  created() {

    window.addEventListener("keydown", (event) => {
      if (this.currentPrompt == null) return

        // Esc!
      if (event.code === "Escape") {
        event.stopImmediatePropagation()
        this.resetPrompts()
      }


    })

  },

  computed: {
    ...mapGetters(["currentPrompt", "currentPromptName"]),
    showOverlay: function () {
      return (
        this.currentPrompt !== null &&
        this.currentPrompt.prompt !== "search" &&
        this.currentPrompt.prompt !== "more"
      )
    },
  },
  methods: {
    resetPrompts() {
      if (this.currentPrompt && this.currentPromptName && this.$refs[this.currentPromptName]) {
        let componentInstance = this.$refs[this.currentPromptName]
        // Check if the component instance has a cancel method
        if (typeof componentInstance.cancel === 'function') {
          componentInstance.cancel()
        }
        else {
          console.warn("Cancel method is missing for a prompt lol")
          this.$store.commit("closeHover")

        }
      }
    },

  },
}
</script>
