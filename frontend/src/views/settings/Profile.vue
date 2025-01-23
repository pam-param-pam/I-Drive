<template>
  <div class="row">
    <div class="column">
      <form class="card" @submit.prevent="saveSettings">
        <div class="card-title">
          <h2>{{ $t("settings.profileSettings") }}</h2>
        </div>

        <div class="card-content">
          <p>
            <input type="checkbox" v-model="hideLockedFolders"/>
            {{ $t("settings.hideLockedFolders") }}

          </p>
          <p>
            <input type="checkbox" v-model="subfoldersInShares"/>
            {{ $t("settings.subfoldersInShares") }}
          </p>
          <p>
            <input type="checkbox" v-model="dateFormat"/>
            {{ $t("settings.setDateFormat") }}
          </p>
          <p>
            <input type="checkbox" v-model="keepCreationTimestamp"/>
            {{ $t("settings.keepCreationTimestamp") }}
          </p>
          <div>
            <h3>{{ $t("settings.concurrentUploadRequests") }}</h3>
            <input
              class="input"
              type="number"
              v-model="concurrentUploadRequests"
            />
          </div>

          <h3>{{ $t("settings.encryptionMethod") }}</h3>
          <EncryptionMethod
            class="input input--block"
            v-model:encryptionMethod="encryptionMethod"
          ></EncryptionMethod>

          <h3>{{ $t("settings.language") }}</h3>
          <languages
            class="input input--block"
            v-model:locale="locale"
          ></languages>

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
      <form class="card" @submit.prevent="savePassword">
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
import Languages from "@/components/settings/Languages.vue"
import {changePassword, updateSettings} from "@/api/user.js"
import router from "@/router/index.js"
import throttle from "lodash.throttle"
import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"
import EncryptionMethod from "@/components/settings/EncryptionMethod.vue"


export default {
   name: "profileSettings",
   components: {
      Languages,
      EncryptionMethod,
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
         concurrentUploadRequests: 4,
         encryptionMethod: null,
         keepCreationTimestamp: false

      }
   },
   computed: {
      ...mapState(useMainStore, ["user", "settings"]),
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
      this.dateFormat = this.settings.dateFormat
      this.concurrentUploadRequests = this.settings.concurrentUploadRequests
      this.encryptionMethod = this.settings.encryptionMethod
      this.keepCreationTimestamp = this.settings.keepCreationTimestamp

   },
   methods: {
      ...mapActions(useMainStore, ["setLoading", "setToken", "updateSettings"]),

      savePassword: throttle(async function (event) {
         if (this.password !== this.passwordConf || this.password === "") {
            return
         }

         let data = {current_password: this.currentPassword, new_password: this.password}

         let res = await changePassword(data)

         localStorage.setItem("token", res.auth_token)
         this.setToken(res.auth_token)
         this.$toast.success(this.$t("settings.passwordUpdated"))
         setTimeout(() => {
            router.go(0)
         }, 2000)

      }, 1000),

      saveSettings: throttle(async function (event) {
         const data = {
            locale: this.locale,
            subfoldersInShares: this.subfoldersInShares,
            hideLockedFolders: this.hideLockedFolders,
            dateFormat: this.dateFormat,
            concurrentUploadRequests: this.concurrentUploadRequests,
            encryptionMethod: this.encryptionMethod,
            keepCreationTimestamp: this.keepCreationTimestamp,

         }

         await updateSettings(data)
         this.updateSettings(data)

         this.$toast.success(this.$t("settings.settingsUpdated"))

      }, 1000),

   },
}
</script>
