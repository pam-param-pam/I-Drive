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
               :disabled="disabledCreation || !currentFolder || searchActive"
               :title="$t('sidebar.newFolder')"
               class="action"
               @click="showHover('newFolder')"
            >
               <i class="material-icons">create_new_folder</i>
               <span>{{ $t("sidebar.newFolder") }}</span>
            </button>

            <button
               :aria-label="$t('sidebar.newFile')"
               :disabled="disabledCreation || !currentFolder || searchActive"
               :title="$t('sidebar.newFile')"
               class="action"
               @click="showHover('newFile')"
            >
               <i class="material-icons">note_add</i>
               <span>{{ $t("sidebar.newFile") }}</span>
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
         @click="showHover('fileStats')"
      >
         <progress-bar :val="Math.round((usage.used / usage.total) * 100)" size="small"></progress-bar>
         <br />
         {{ filesize(usage.used) }} of {{ filesize(usage.total) }} used
      </div>

      <p class="credits">
         <span>
            <a :href="repoLink" rel="noopener noreferrer" target="_blank"
            >{{ name }} By {{ author }} v.{{ version }}</a
            >
         </span>
      </p>

      <div class="sidebar-actions-row">
         <dark-mode-button />

         <div class="notif-wrapper" v-if="isLogged">
            <button
               :aria-label="$t('sidebar.notifications')"
               :title="$t('sidebar.notifications')"
               class="action action--notifications"
               :class="{ 'notif-alert': highlightNotification }"
               @click="toggleNotifications"
            >
               <i class="material-icons">notifications</i>
               <span v-if="user.unreadNotifications" class="notif-badge">{{ user.unreadNotifications }}</span>
               <span class="notif-ripple" v-if="highlightNotification"></span>
            </button>
         </div>

      </div>
      <div v-if="selectedFile && !isMobile() && settings.itemInfoShortcut" class="selected-file-info">
         <p><strong>{{ $t("prompts.name") }}: </strong> {{ selectedFile.name }}</p>
         <p><strong>{{ $t("prompts.id") }}: </strong> {{ selectedFile.id }}</p>
         <p v-if="!selectedFile.isDir"><strong>{{ $t("prompts.type") }}: </strong> {{ selectedFile.type }}</p>
         <p v-if="!selectedFile.isDir"><strong>{{ $t("prompts.isEncrypted") }}: </strong>
            <span :style="{ color: selectedFile.encryption_method !== 0 ? 'green' : 'red' }">
              {{ selectedFile.encryption_method !== 0 ? "\u2705" : "\u274C" }}
            </span>
         </p>
         <p v-if="!selectedFile.isDir"><strong>{{ $t("prompts.size") }}: </strong> {{ filesize(selectedFile.size) }}</p>
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
         repoLink: githubUrl,
         lastFolderId: null,
         highlightNotification: false
      }
   },

   computed: {
      ...mapState(useMainStore, ["items", "usage", "settings", "user", "perms", "currentFolder", "disabledCreation", "isLogged", "currentPrompt", "loading", "searchActive", "searchItems", "selected", "sortedItems"]),
      selectedFile() {
         if (this.selected.length > 1) return null
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
      },
      "user.unreadNotifications"(newVal, oldVal) {
         if (newVal > oldVal) {
            this.signalNewNotification()
         }
      }
   },
   methods: {
      isMobile,
      filesize,
      ...mapActions(useMainStore, ["closeHover", "showHover", "setUsage"]),
      toggleNotifications() {
         this.showHover("notifications")
      },
      signalNewNotification() {
         this.highlightNotification = true
         setTimeout(() => {
            this.highlightNotification = false
         }, 800)
      },
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
         const currentId = this.currentFolder?.id || this.user.root

         // Called twice on same folder, or called in Files go to absolute root
         if (this.lastFolderId === currentId || this.$route.name === "Files") {

            this.$router.push({ name: "Files", params: { folderId: this.user.root } })
         } else {
            // Normal navigation
            this.$router.push({ name: "Files", params: { folderId: currentId } })
         }

         this.lastFolderId = currentId
         this.closeHover()
      },

      toTrash() {
         this.lastFolderId = null
         this.$router.push({ name: `Trash` })
         this.closeHover()
      },

      toSettings() {
         this.lastFolderId = null
         this.$router.push({ name: `Settings` })
         this.closeHover()
      },


      logout: auth.logout
   }
}
</script>
<style scoped>
.selected-file-info {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  background: var(--background);
  padding: 0.75rem 1rem 1rem;
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
  max-width: 16em;
}

.selected-file-info strong {
  font-weight: bold;
}

.sidebar-actions-row {
  display: flex;
  align-items: center;
  position: relative;
}

.notif-badge {
  position: absolute;
  top: 8px;
  left: 40px;
  background: #e57373;
  color: var(--textPrimary);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
}

.action--notifications:hover {
  background: transparent !important;
  box-shadow: none !important;
  transform: none !important;
}

.action--notifications {
  padding-right: 15px;
  padding-left: 15px;

}

/* subtle glow */
.notif-alert {
  position: relative;
  box-shadow: 0 0 0 3px rgba(229, 115, 115, 0.5);
  border-radius: 8px;
}

/* ripple effect */
.notif-ripple {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 10px;
  height: 10px;
  background: rgba(229, 115, 115, 0.6);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  animation: ripple 1.2s ease-out forwards;
  pointer-events: none;
}

@keyframes ripple {
  0% {
    width: 10px;
    height: 10px;
    opacity: 0.7;
  }
  100% {
    width: 80px;
    height: 80px;
    opacity: 0;
  }
}
</style>