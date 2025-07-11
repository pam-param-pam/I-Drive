<template>
  <nav :class="{ active }">
    <template v-if="isLogged">
      <button
        :aria-label="$t('sidebar.myFiles')"
        :title="$t('sidebar.myFiles')"
        class="action"
        @click="toRoot"
      >
        <i class="material-icons">folder</i>
        <span>{{ $t("sidebar.myFiles") }}</span>
      </button>

      <div v-if="perms.create">
        <button
          :aria-label="$t('sidebar.newFolder')"
          :disabled="disabledCreation || !currentFolder"
          :title="$t('sidebar.newFolder')"
          class="action"
          @click="showHover('newFolder')"
        >
          <i class="material-icons">create_new_folder</i>
          <span>{{ $t("sidebar.newFolder") }}</span>
        </button>
      </div>

      <button
        :aria-label="$t('sidebar.trash')"
        :title="$t('sidebar.trash')"
        class="action"
        @click="toTrash"
      >
        <i class="material-icons">delete</i>
        <span>{{ $t("sidebar.trash") }}</span>
      </button>

      <div>
        <button
          :aria-label="$t('sidebar.settings')"
          :title="$t('sidebar.settings')"
          class="action"
          @click="toSettings"
        >
          <i class="material-icons">settings_applications</i>
          <span>{{ $t("sidebar.settings") }}</span>
        </button>

        <button
          id="logout"
          :aria-label="$t('sidebar.logout')"
          :title="$t('sidebar.logout')"
          class="action"
          @click="logout"
        >
          <i class="material-icons">exit_to_app</i>
          <span>{{ $t("sidebar.logout") }}</span>
        </button>
      </div>
    </template>
    <template v-else>
      <router-link
        :aria-label="$t('sidebar.login')"
        :title="$t('sidebar.login')"
        class="action"
        to="/login"
      >
        <i class="material-icons">exit_to_app</i>
        <span>{{ $t("sidebar.login") }}</span>
      </router-link>

      <router-link
        v-if="signup"
        :aria-label="$t('sidebar.register')"
        :title="$t('sidebar.register')"
        class="action"
        to="/login"
      >
        <i class="material-icons">person_add</i>
        <span>{{ $t("sidebar.register") }}</span>
      </router-link>
    </template>

    <div
      v-if="$route.name === 'Files' && (!disabledCreation || searchActive)"
      class="credits"
      style="width: 80%; margin: 2em 2.5em 3em 2.5em"
    >
      <progress-bar :val="Math.round((usage.used / usage.total) * 100)" size="small" @click="showHover('fileStats')"></progress-bar>
      <br />
      {{ filesize(usage.used) }} of {{ filesize(usage.total) }} used
    </div>

    <p class="credits">
         <span>
            <a :href="repoLink" rel="noopener noreferrer" target="_blank"
            >{{ name }} By {{ author }} v.{{ version }}</a
            >
         </span>
      <span>
            <a @click="help">{{ $t("sidebar.help") }}</a>
         </span>
    </p>
    <dark-mode-button />

    <div v-if="selectedFile && !isMobile() && shellSettings.showFileInfoInSidebar" class="selected-file-info">
      <p><strong>Name:</strong> {{ selectedFile.name }}</p>
      <p><strong>ID:</strong> {{ selectedFile.id }}</p>
      <p v-if="selectedFile.size"><strong>Size:</strong> {{ filesize(selectedFile.size) }}</p>
    </div>
  </nav>
</template>

<script>
import * as auth from "@/utils/auth"
import { githubUrl, signup, version } from "@/utils/constants"
import { getUsage } from "@/api/folder.js"
import { author, name } from "@/utils/constants.js"
import { filesize } from "@/utils/index.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import DarkModeButton from "@/components/sidebar/DarkModeButton.vue"
import ProgressBar from "@/components/sidebar/SimpleProgressBar.vue"
import { isMobile } from "@/utils/common.js"

export default {
   name: "sidebar",

   components: {
      DarkModeButton,
      ProgressBar
   },

   data() {
      return {
         name: name,
         author: author,
         repoLink: githubUrl
      }
   },

   computed: {
      ...mapState(useMainStore, ["items", "usage", "shellSettings", "user", "perms", "currentFolder", "disabledCreation", "isLogged", "currentPrompt", "loading", "searchActive", "searchItems", "selected", "sortedItems"]),
      selectedFile() {
         return this.selected[0]
      },
      active() {
         return this.currentPrompt?.prompt === "sidebar"
      },
      signup: () => signup,
      version: () => version
   },
   async created() {
       await this.fetchUsage()
   },
   watch: {
      async currentFolder() {
         await this.fetchUsage()
      },
      async searchItems() {
         await this.fetchUsage()
      }
   },
   methods: {
      isMobile,
      filesize,
      ...mapActions(useMainStore, ["closeHover", "showHover", "setUsage"]),

      async fetchUsage() {
         if (this.currentFolder && (this.$route.name === "Files" || this.$route.name === "Preview")) {
            if (!this.searchActive) {
               let usage = await getUsage(this.currentFolder?.id, this.currentFolder?.lockFrom)
               this.setUsage({
                  total: usage.total,
                  used: usage.used
               })
            } else {
               let searchUsed = (this.searchItems || []).reduce((total, item) => {
                  let size = Number(item.size) || 0
                  return total + size
               }, 0)

               this.setUsage({
                  used: searchUsed,
                  total: this.usage.total
               })
            }
         }
      },

      toRoot() {
         // let folderId = this.currentFolder?.id || this.user.root
         let folderId = this.user.root
         this.$router
            .push({ name: `Files`, params: { folderId: folderId } })
            .catch((err) => {
            })
         this.closeHover()
      },

      toTrash() {
         this.$router.push({ name: `Trash` }).catch((err) => {
         })
         this.closeHover()
      },

      toSettings() {
         this.$router.push({ name: `Settings` }).catch((err) => {
         })
         this.closeHover()
      },

      help() {
         this.showHover("help")
      },

      logout: auth.logout
   }
}
</script>
<style scoped>
.selected-file-info {
 position: fixed;
 bottom: 1rem;
 left: 0;
 width: 100%;
 background: rgba(0, 0, 0, 0.05);
 padding: 0.75rem 1rem;
 font-size: 0.9rem;
 text-align: left;

}

.selected-file-info h4,
.selected-file-info p {
 margin: 0.25rem 0;
 font-size: 0.85rem;
 word-wrap: break-word;
 overflow-wrap: break-word;
 white-space: normal;
 max-width: 16em; /* Prevents text from exceeding the container width */
}

.selected-file-info strong {
 font-weight: bold;
}
</style>