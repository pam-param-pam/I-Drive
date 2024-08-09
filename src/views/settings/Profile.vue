<template>
  <div class="row">
    <div class="column">
      <form class="card" @submit="updateSettings">
        <div class="card-title">
          <h2>{{ $t("settings.profileSettings") }}</h2>
        </div>

        <div class="card-content">
          <p>
            <input type="checkbox" v-model="hideLockedFolders" />
            {{ $t("settings.hideLockedFolders") }}

          </p>
          <p>
            <input type="checkbox" v-model="subfoldersInShares" />
            {{ $t("settings.subfoldersInShares") }}
          </p>
          <p>
            <input type="checkbox" v-model="dateFormat" />
            {{ $t("settings.setDateFormat") }}
          </p>

          <div>
            <h3>{{ $t("settings.webhookURL") }}</h3>
            <input
              class="input input--block"
              type="text"
              v-model="webhook"
            />
          </div>

          <h3>{{ $t("settings.language") }}</h3>
          <languages
            class="input input--block"
            :locale.sync="locale"
          ></languages>

          <p>
            <label for="theme">{{ $t("settings.themes.title") }}</label>
            <themes
              class="input input--block"
              :theme.sync="theme"
              id="theme"
            ></themes>
          </p>

        </div>

        <div class="card-action">
          <input
            class="button button--flat"
            type="submit"
            :value="$t('buttons.update')"
          />
        </div>
      </form>
    </div>

    <div class="column">
      <form class="card" v-if="!user.lockPassword" @submit="updatePassword">
        <div class="card-title">
          <h2>{{ $t("settings.changePassword") }}</h2>
        </div>

        <div class="card-content">
          <input
            class="input input--block"
            type="password"
            :placeholder="$t('settings.currentPassword')"
            v-model="currentPassword"
            name="password"
          />
          <input
            :class="passwordClass"
            type="password"
            :placeholder="$t('settings.newPassword')"
            v-model="password"
            name="password"
          />
          <input
            :class="passwordClass"
            type="password"
            :placeholder="$t('settings.newPasswordConfirm')"
            v-model="passwordConf"
            name="password"
          />
        </div>

        <div class="card-action">
          <input
            class="button button--flat"
            type="submit"
            :value="$t('buttons.update')"
          />
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { mapState, mapMutations } from "vuex"
import Languages from "@/components/settings/Languages.vue"
import Themes from "@/components/settings/Themes.vue"
import {changePassword, updateSettings} from "@/api/user.js"
import router from "@/router/index.js";

export default {
  name: "settings",
  components: {
    Themes,
    Languages,
  },
  data() {
    return {
      password: "",
      currentPassword: "",
      passwordConf: "",
      hideLockedFolders: false,
      subfoldersInShares: false,
      dateFormat: false,
      locale: "",
      webhook: "",
      theme: "",
    }
  },
  computed: {
    ...mapState(["user", "settings"]),
    passwordClass() {
      const baseClass = "input input--block"

      if (this.password === "" && this.passwordConf === "") {
        return baseClass
      }

      if (this.password === this.passwordConf) {
        return `${baseClass} input--green`
      }

      return `${baseClass} input--red`
    },
  },
  created() {
    this.setLoading(false)
    this.locale = this.settings.locale
    this.hideLockedFolders = this.settings.hideLockedFolders
    this.subfoldersInShares = this.settings.subfoldersInShares
    this.webhook = this.settings.webhook
    this.dateFormat = this.settings.dateFormat
  },
  methods: {
    ...mapMutations(["updateUser", "setLoading"]),
    async updatePassword(event) {
      event.preventDefault()

      if (this.password !== this.passwordConf || this.password === "") {
        return
      }

      const data = { current_password: this.currentPassword, new_password: this.password}

      let res = await changePassword(data)



      localStorage.setItem("token", res.auth_token)
      this.$store.commit("setToken", res.auth_token)

      this.$toast.success(this.$t("settings.passwordUpdated"))

      setTimeout(() => {
        router.go(0)
      }, 2000)


    },
    async updateSettings(event) {
      event.preventDefault()

      const data = {
        locale: this.locale,
        subfoldersInShares: this.subfoldersInShares,
        hideLockedFolders: this.hideLockedFolders,
        dateFormat: this.dateFormat,
        webhook: this.webhook
      }
      this.setTheme(this.theme)

      await updateSettings(data)
      this.$store.commit("updateSettings", data)


      this.$toast.success(this.$t("settings.settingsUpdated"))

    },
    getMediaPreference() {
      let hasDarkPreference = window.matchMedia(
        "(prefers-color-scheme: dark)"
      ).matches
      if (hasDarkPreference) {
        return "dark"
      } else {
        return "light"
      }
    },
    setTheme(theme) {
      const html = document.documentElement
      if (!theme) {
        theme = this.getMediaPreference()

        html.className = theme
      } else {
        html.className = theme
      }
    }
  },
}
</script>
