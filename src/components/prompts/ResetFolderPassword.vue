<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.resetFolderPassword") }}</h2>
    </div>

    <div class="card-content">
      <p>{{ $t("prompts.resetMessage") }}:</p>

      <div>
        <input
          class="input input--block styled-input"
          :placeholder="$t('prompts.accountPassword')"
          v-model.trim="accountPassword"
        />
      </div>

      <div>
        <input
          class="input input--block styled-input"
          :placeholder="$t('prompts.newFolderPassword')"
          v-model.trim="folderPassword"


        />
      </div>

      <div class="checkbox-group">
        <label>
          <input
            type="checkbox"
            v-model="pinkyPromise"
          />
          {{ $t("prompts.pinkyPromiseResetFolderPassword") }}
        </label>
      </div>
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="$store.commit('closeHover')"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        @click="submit()"
        class="button button--flat"
        type="submit"
        :disabled="!pinkyPromise || accountPassword === ''"
        :aria-label="$t('buttons.reset')"
        :title="$t('buttons.reset')"
      >
        {{ $t("buttons.reset") }}
      </button>
    </div>
  </div>
</template>

<script>
import {mapGetters, mapMutations} from "vuex"
import {resetPassword} from "@/api/folder.js"

export default {
  name: "resetFolderPassword",
  props: {
    folderId: String,
    lockFrom: String,
  },
  data() {
    return {
      accountPassword: "",
      folderPassword: "",
      pinkyPromise: false,
    }
  },
  computed: {
  ...mapGetters(["currentPrompt"]),
  },
  methods: {
    ...mapMutations(["closeHover", "setFolderPassword"]),

    async submit() {
      if (!this.pinkyPromise) {
        alert(this.$t("prompts.pinkyPromiseError"))
        return
      }

      try {
        let res =  await resetPassword(this.folderId, this.accountPassword, this.folderPassword)
        let message = this.$t('toasts.passwordIsBeingUpdated')
        this.$toast.info(message, {
          timeout: null,
          id: res.task_id,
        })
        this.setFolderPassword({ "folderId": this.folderId, "password": this.folderPassword })

        this.currentPrompt.confirm()
        this.closeHover()

      } catch (error) {
        console.error("Error resetting password:", error)
      }
    },
  },
}
</script>

<style scoped>
.checkbox-group {
 margin-bottom: 15px;
}
</style>
