<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.unlockFolder") }}</h2>
    </div>

    <div class="card-content">
      <p>
        {{ $t("prompts.enterFolderPassword") }} <code>{{ folder.name }}</code>

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
import {mapGetters, mapMutations, mapState} from "vuex"
import {isPasswordCorrect} from "@/api/item.js"
import store from "@/store/index.js"
import i18n from "@/i18n/index.js"

export default {
  name: "folder-password",
  data() {
    return {
      password: "",
    }
  },
  props: {
    requiredFolderPasswords: [],
  },

  beforeDestroy() {

  },
  computed: {
    ...mapGetters(["currentPrompt", "getFolderPassword", "currentPromptName"]),
    ...mapState(["selected", "loading"]),
    folder() {
      return this.requiredFolderPasswords[0]
    }
  },
  methods: {
    ...mapMutations(["closeHover", "setFolderPassword", "closeHovers", "setLoading"]),
    async submit() {
      if (await isPasswordCorrect(this.folder.id, this.password) === true) {
        this.setFolderPassword({ "folderId": this.folder.id, "password": this.password })

        this.finishAndShowAnotherPrompt()

      } else {
        let message = this.$t('toasts.folderPasswordIncorrect')
        this.$toast.error(message)
      }
    },
    cancel() {
      if (this.loading) store.commit("setError", { "response": { "status": 469 } })
      store.commit("setLoading", false)
      this.$toast.error(i18n.t("toasts.passwordIsRequired"))

      this.closeHover()
    },
    finishAndShowAnotherPrompt() {
      console.log("finishAndShowAnotherPrompt")

      let requiredFolderPasswordsCopy = [...this.requiredFolderPasswords]
      requiredFolderPasswordsCopy.shift()

      if (requiredFolderPasswordsCopy.length === 0) {

        let confirmFunc = this.currentPrompt.confirm
        this.closeHover()
        if (confirmFunc) confirmFunc()

      }
      else {
        console.log("showHovershowHovershowHover")
        let confirm = this.currentPrompt.confirm
        this.closeHover()
        this.$nextTick(() => {

          store.commit("showHover", {
            prompt: "FolderPassword",
            props: {requiredFolderPasswords: requiredFolderPasswordsCopy},

            confirm: confirm
          })
        })

      }
    },
    onPasswordReset() {
      console.log("onPasswordReset")
      this.finishAndShowAnotherPrompt()

    },
    forgotPassword() {
      store.commit("showHover", {
        prompt: "ResetFolderPassword",
        props: {folderId: this.folder.id, lockFrom: this.folder.lockFrom},

        confirm: () => {
          this.onPasswordReset()
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
