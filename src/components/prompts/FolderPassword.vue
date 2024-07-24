<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.unlockFolder") }}</h2>
    </div>

    <div class="card-content">
      <p>
        {{ $t("prompts.enterFolderPassword") }}
      </p>
      <input
        class="input input--block"
        v-focus
        type="text"
        @keyup.enter="submit()"
        v-model.trim="password"
      />
      <!-- Forgot Password Button added below the input -->
      <button
        @click="forgotPassword()"
        class="button button--small button--text-blue"
        :aria-label="$t('buttons.forgotFolderPassword')"
        :title="$t('buttons.forgotFolderPassword')"
      >
        {{ $t("buttons.forgotFolderPassword") }}
      </button>
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="cancel()"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        @click="submit()"
        class="button button--flat"
        type="submit"
        :aria-label="$t('buttons.submit')"
        :title="$t('buttons.submit')"
      >
        {{ $t("buttons.unlock") }}
      </button>
    </div>
  </div>
</template>

<script>
import { mapGetters, mapMutations, mapState } from "vuex"
import { isPasswordCorrect } from "@/api/item.js"
import store from "@/store/index.js";
import vue from "@/utils/vue.js";
import i18n from "@/i18n/index.js";
import {backend_instance} from "@/api/networker.js";

export default {
  name: "folder-password",
  data() {
    return {
      password: "",
    }
  },
  props: {
    folderId: String,
    lockFrom: String,
  },
  computed: {
    ...mapGetters(["currentPrompt", "getFolderPassword", "isLoading"]),
    ...mapState(["selected", "loading"]),
  },
  methods: {
    ...mapMutations(["closeHover", "setFolderPassword"]),
    async submit() {
      if (await isPasswordCorrect(this.folderId, this.password) === true) {
        this.setFolderPassword({ "folderId": this.lockFrom, "password": this.password })
        this.currentPrompt.confirm()
        this.closeHover()
      } else {
        let message = this.$t('toasts.folderPasswordIncorrect')
        this.$toast.error(message)
      }
    },
    cancel() {
      if (this.currentPrompt.cancel) this.currentPrompt.cancel()
      if (this.loading) store.commit("setError", { "response": { "status": 469 } })
      store.commit("setLoading", false)

      this.closeHover()
    },
    forgotPassword() {
      store.commit("showHover", {
        prompt: "ResetFolderPassword",
        props: {folderId: this.folderId, lockFrom: this.lockFrom},

        confirm: () => {
          this.closeHover()
          this.currentPrompt.confirm()

        },
      })
    }
  },
}
</script>

<style scoped>
.button--small {
 font-size: 0.875rem;
 padding: 0.5rem 1rem;
 border: none;
 background: none;
 color: #3a96f6;

}

.button--small:hover {
 text-decoration: underline;
 background: none;

}
</style>
