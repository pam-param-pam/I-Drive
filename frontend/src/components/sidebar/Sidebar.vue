<template>
  <nav :class="{ active }">
    <template v-if="isLogged">
      <button
        class="action"
        @click="toRoot"
        :aria-label="$t('sidebar.myFiles')"
        :title="$t('sidebar.myFiles')"
      >
        <i class="material-icons">folder</i>
        <span>{{ $t("sidebar.myFiles") }}</span>
      </button>

      <div v-if="perms.create">
        <button
          :disabled="disabledCreation || !currentFolder"
          @click="showHover('newDir')"
          class="action"
          :aria-label="$t('sidebar.newFolder')"
          :title="$t('sidebar.newFolder')"
        >
          <i class="material-icons">create_new_folder</i>
          <span>{{ $t("sidebar.newFolder") }}</span>
        </button>

      </div>

      <button
        class="action"
        @click="toTrash"
        :aria-label="$t('sidebar.trash')"
        :title="$t('sidebar.trash')"
      >
        <i class="material-icons">delete</i>
        <span>{{ $t("sidebar.trash") }}</span>
      </button>

      <div class="bottom-buttons(TODO)">
        <button
          class="action"
          @click="toSettings"
          :aria-label="$t('sidebar.settings')"
          :title="$t('sidebar.settings')"
        >
          <i class="material-icons">settings_applications</i>
          <span>{{ $t("sidebar.settings") }}</span>
        </button>

        <button
          @click="logout"
          class="action"
          :aria-label="$t('sidebar.logout')"
          id="logout"
          :title="$t('sidebar.logout')"
        >
          <i class="material-icons">exit_to_app</i>
          <span>{{ $t("sidebar.logout") }}</span>
        </button>
      </div>
    </template>
    <template v-else>
      <router-link
        class="action"
        to="/login"
        :aria-label="$t('sidebar.login')"
        :title="$t('sidebar.login')"
      >
        <i class="material-icons">exit_to_app</i>
        <span>{{ $t("sidebar.login") }}</span>
      </router-link>

      <router-link
        v-if="signup"
        class="action"
        to="/login"
        :aria-label="$t('sidebar.register')"
        :title="$t('sidebar.register')"
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
      <progress-bar :val="usage.usedPercentage" size="small"></progress-bar>
      <br />
      {{ usage.used }} of {{ usage.total }} used
    </div>

    <p class="credits">
      <span>
        <a
          rel="noopener noreferrer"
          target="_blank"
          :href=repoLink
        >{{ name }} By {{ author }} v.{{ version }}</a
        >
      </span>
      <span>
        <a @click="help">{{ $t("sidebar.help") }}</a>
      </span>
    </p>
    <dark-mode-button />
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
         usage: { used: "0 B", total: "0 B", usedPercentage: 0 }
      }
   },
   computed: {
      ...mapState(useMainStore, ["user", "perms", "currentFolder", "disabledCreation", "isLogged", "currentPrompt", "loading", "searchActive", "searchItems"]),
      active() {
         return this.currentPrompt?.prompt === "sidebar"
      },
      signup: () => signup,
      version: () => version
   },
   async mounted() {
      await this.fetchUsage()

   },
   watch: {
      async currentFolder() {
         await this.fetchUsage()
      },
      async searchItems() {
         console.log("AAAAAAAAAAAAAAAAAAAAAAAAA")
         await this.fetchUsage()
      }
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover", "showHover"]),
      async fetchUsage() {
         if (this.currentFolder && this.$route.name === "Files") {
            if (!this.searchActive) {
               let usage = await getUsage(this.currentFolder?.id, this.currentFolder?.lockFrom)
               this.usage = {
                  totalBytes: usage.total,
                  used: filesize(usage.used),
                  total: filesize(usage.total),
                  usedPercentage: Math.round((usage.used / usage.total) * 100)
               }
            } else {
               let used = (this.searchItems || []).reduce((total, item) => {
                  let size = Number(item.size) || 0
                  return total + size
               }, 0)
               this.usage.usedPercentage = Math.round((used / this.usage.totalBytes) * 100)
               this.usage.used = filesize(used)
            }
         }
      },
      toRoot() {
         this.$router.push({ name: `Files`, params: { folderId: this.user.root } }).catch(err => {
         })
         this.closeHover()
      },
      toTrash() {
         this.$router.push({ name: `Trash` }).catch(err => {
         })
         this.closeHover()
      },
      toSettings() {
         this.$router.push({ name: `Settings` }).catch(err => {
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

