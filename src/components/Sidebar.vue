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
          :disabled="disableCreation"
          @click="$store.commit('showHover', 'newDir')"
          class="action"
          :aria-label="$t('sidebar.newFolder')"
          :title="$t('sidebar.newFolder')"
        >
          <i class="material-icons">create_new_folder</i>
          <span>{{ $t("sidebar.newFolder") }}</span>
        </button>

        <button
          :disabled="disableCreation"
          @click="$store.commit('showHover', 'newFile')"
          class="action"
          :aria-label="$t('sidebar.newFile')"
          :title="$t('sidebar.newFile')"
        >
          <i class="material-icons">note_add</i>
          <span>{{ $t("sidebar.newFile") }}</span>
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
      v-if="$router.currentRoute.path.includes('/files/') && !disableCreation"
      class="credits"
      style="width: 90%; margin: 2em 2.5em 3em 2.5em"
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
          href="https://github.com/pam-param-pam/Disney-Plus-api-wrapper"
          >File Browser {{ version }}</a
        >
      </span>
      <span>
        <a @click="help">{{ $t("sidebar.help") }}</a>
      </span>
    </p>
  </nav>
</template>

<script>
import { mapState, mapGetters } from "vuex"
import * as auth from "@/utils/auth"
import { version, signup } from "@/utils/constants"
import ProgressBar from "vue-simple-progress"
import prettyBytes from "pretty-bytes"
import {getUsage} from "@/api/folder.js"

export default {
  name: "sidebar",
  components: {
    ProgressBar,
  },
  computed: {
    ...mapState(["user", "perms", "currentFolder", "disableCreation"]),
    ...mapGetters(["isLogged", "currentPrompt"]),
    active() {
      return this.currentPrompt?.prompt === "sidebar"
    },
    signup: () => signup,
    version: () => version,
  },
  asyncComputed: {
    usage: {
      async get() {
        if (this.currentFolder) {
          let usageStats = { used: 0, total: 0, usedPercentage: 0 }

          try {
            let usage = await getUsage(this.currentFolder?.id, this.currentFolder?.lockFrom)
            usageStats = {
              used: prettyBytes(usage.used, { binary: true }),
              total: prettyBytes(usage.total, { binary: true }),
              usedPercentage: Math.round((usage.used / usage.total) * 100),
            }
          } catch (error) {
            console.log(error)
          }
          return usageStats
        }
        return this.usage

      },
      default: { used: "0 B", total: "0 B", usedPercentage: 0 },
        
    },
  },
  methods: {
    toRoot() {
      //this.$store.commit("setOpenSearchState", false)
      //this.$store.commit("setIsTrash", false)
      this.$router.push({name: `Files`, params: {folderId: this.user.root}}).catch(err => {})
      //this.$router.go(0)
      this.$store.commit("closeHover")
    },
    toTrash() {
      //this.$store.commit("setOpenSearchState", false)
      this.$router.push({name: `Trash`}).catch(err => {})
      this.$store.commit("closeHover")
    },
    toSettings() {
      this.$router.push({name: `Settings`}).catch(err => {})
      this.$store.commit("closeHover")
    },
    help() {
      this.$store.commit("showHover", "help")
    },
    logout: auth.logout,
  },
}
</script>
<style>


</style>
