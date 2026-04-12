<template>
   <div class="row">
      <div class="column">
         <form class="card" @submit.prevent="saveSettings">
            <div class="card-title">
               <h2>{{ $t("settings.profileSettings") }}</h2>
            </div>

            <div class="card-content">
               <p>
                  <label>
                     <input v-model="hideLockedFolders" type="checkbox" />
                     {{ $t("settings.hideLockedFolders") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="subfoldersInShares" type="checkbox" />
                     {{ $t("settings.subfoldersInShares") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="dateFormat" type="checkbox" />
                     {{ $t("settings.setDateFormat") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="keepCreationTimestamp" type="checkbox" />
                     {{ $t("settings.keepCreationTimestamp") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="popupPreview" type="checkbox" />
                     {{ $t("settings.popupPreview") }}
                  </label>
               </p>

               <p>
                  <label>
                     <input v-model="itemInfoShortcut" type="checkbox" />
                     {{ $t("settings.itemInfoShortcut") }}
                  </label>
               </p>

               <div>
                  <label>
                     <h3>{{ $t("settings.concurrentUploadRequests") }}</h3>
                     <input v-model="concurrentUploadRequests" class="input" type="number" />
                  </label>

               </div>

               <h3>{{ $t("settings.encryptionMethod") }}</h3>
               <EncryptionMethod
                  v-model:encryptionMethod="encryptionMethod"
                  class="input input--block"
               ></EncryptionMethod>

               <h3>{{ $t("settings.language") }}</h3>
               <languages v-model:locale="locale" class="input input--block"></languages>
            </div>

            <div class="card-action">
               <input :value="$t('buttons.update')" class="button button--flat" type="submit" />
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
                  v-model="currentPassword"
                  :placeholder="$t('settings.currentPassword')"
                  class="input input--block"
                  name="password"
                  type="password"
               />
               <input
                  v-model="password"
                  :class="passwordClass"
                  :placeholder="$t('settings.newPassword')"
                  name="password"
                  type="password"
               />
               <input
                  v-model="passwordConf"
                  :class="passwordClass"
                  :placeholder="$t('settings.newPasswordConfirm')"
                  name="password"
                  type="password"
               />
            </div>

            <div class="card-action">
               <input :value="$t('buttons.update')" class="button button--flat" type="submit" />
            </div>
         </form>
      </div>
   </div>
</template>

<script>
import Languages from "@/components/settings/Languages.vue"
import { updateSettings } from "@/api/user.js"
import router from "@/router/index.js"
import throttle from "lodash.throttle"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import EncryptionMethod from "@/components/settings/EncryptionMethod.vue"
import { changePassword } from "@/api/auth.js"

export default {
   name: "profile",

   components: {
      Languages,
      EncryptionMethod
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
         keepCreationTimestamp: false,
         popupPreview: false,
         itemInfoShortcut: false
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
      }
   },

   created() {
      this.locale = this.settings.locale
      this.hideLockedFolders = this.settings.hideLockedFolders
      this.subfoldersInShares = this.settings.subfoldersInShares
      this.dateFormat = this.settings.dateFormat
      this.concurrentUploadRequests = this.settings.concurrentUploadRequests
      this.encryptionMethod = this.settings.encryptionMethod
      this.keepCreationTimestamp = this.settings.keepCreationTimestamp
      this.popupPreview = this.settings.popupPreview
      this.itemInfoShortcut = this.settings.itemInfoShortcut
   },

   methods: {
      ...mapActions(useMainStore, ["setToken", "updateSettings", "setDeviceId"]),
      savePassword: throttle(async function(event) {
         //todo move this somewhere
         if (this.password !== this.passwordConf || this.password === "") {
            return
         }

         let data = { current_password: this.currentPassword, new_password: this.password }
         let device_id = localStorage.getItem("device_id")
         localStorage.setItem("device_id", ".") // change it so force logout will not affect this tab
         let toastId
         let res
         try {
            toastId = this.$toast.info(this.$t("toasts.updatingPassword"), {timeout: null})
            res = await changePassword(data)

         } catch(e) {
            this.$toast.dismiss(toastId)
            localStorage.setItem("device_id", device_id)
            throw e
         }
         localStorage.setItem("token", res.auth_token)
         localStorage.setItem("device_id", res.device_id)

         this.setToken(res.auth_token)
         this.setDeviceId(res.device_id)

         this.$toast.update(toastId, {
            content: this.$t("toasts.passwordUpdated"),
            options: { type: "success" }
         }, true)

         setTimeout(() => {
            router.go(0)
         }, 1000)
      }, 1000),

      saveSettings: throttle(async function(event) {
         if (this.concurrentUploadRequests <= 0) {
            this.$toast.error(this.$t("settings.concurrentUploadRequestsIsNegative"))
            return
         }
         let data = {
            locale: this.locale,
            subfoldersInShares: this.subfoldersInShares,
            hideLockedFolders: this.hideLockedFolders,
            dateFormat: this.dateFormat,
            concurrentUploadRequests: this.concurrentUploadRequests,
            encryptionMethod: this.encryptionMethod,
            keepCreationTimestamp: this.keepCreationTimestamp,
            popupPreview: this.popupPreview,
            itemInfoShortcut: this.itemInfoShortcut
         }

         await updateSettings(data)
         this.updateSettings(data)

         this.$toast.success(this.$t("settings.settingsUpdated"))
      }, 1000)
   }
}
</script>
