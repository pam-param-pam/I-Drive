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
import Help from "./Help.vue";
import Info from "./Info.vue";
import Delete from "./Delete.vue";
import Rename from "./Rename.vue";
import Download from "./Download.vue";
import Move from "./Move.vue";
import NewFile from "./NewFile.vue";
import NewDir from "./NewDir.vue";
import DiscardEditorChanges from "./DiscardEditorChanges.vue";
import Share from "./Share.vue";
import Upload from "./Upload.vue";
import ShareDelete from "./ShareDelete.vue";
import Sidebar from "../Sidebar.vue";
import { mapGetters } from "vuex";
import buttons from "@/utils/buttons";
import FolderPassword from "@/components/prompts/FolderPassword.vue";
import EditFolderPassword from "@/components/prompts/EditFolderPassword.vue";

export default {
  name: "prompts",
  components: {
    Info,
    Delete,
    Rename,
    Download,
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
  },
  data: function () {
    return {
      pluginData: {
        buttons,
        store: this.$store,
        router: this.$router,
      },
    };
  },
  created() {

    window.addEventListener("keydown", (event) => {
      if (this.currentPrompt == null) return;

        // Esc!
      if (event.code === "Escape") {
        event.stopImmediatePropagation();
        this.$store.commit("closeHover");
      }


    });

  },

  computed: {
    ...mapGetters(["currentPrompt", "currentPromptName"]),
    showOverlay: function () {
      return (
        this.currentPrompt !== null &&
        this.currentPrompt.prompt !== "search" &&
        this.currentPrompt.prompt !== "more"
      );
    },
  },
  methods: {
    resetPrompts() {
      this.$store.commit("closeHover");
    },
  },
};
</script>
