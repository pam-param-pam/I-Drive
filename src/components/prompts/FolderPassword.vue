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
import { mapGetters, mapMutations, mapState } from "vuex"
import { isPasswordCorrect } from "@/api/item.js"
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
  created() {
    console.log("requiredFolderPasswords")

    console.log(this.requiredFolderPasswords)
  },
  beforeDestroy() {
    console.log("aaaaaaaa")

    console.log(this.requiredFolderPasswords)
  },
  computed: {
    ...mapGetters(["currentPrompt", "getFolderPassword"]),
    ...mapState(["selected", "loading"]),
    folder() {
      let folder = this.requiredFolderPasswords[0]
      console.log("folder")
      console.log(folder)
      return folder
    }
  },
  methods: {
    ...mapMutations(["closeHover", "setFolderPassword", "closeHovers"]),
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
        if (this.currentPrompt.confirm) this.currentPrompt.confirm()
        this.closeHovers()

      }
      else {
        console.log("showHovershowHovershowHover")
        console.log(requiredFolderPasswordsCopy)
        let confirm = this.currentPrompt.confirm
        this.closeHover()
        this.$nextTick(() => {

          store.commit("showHover", {
            prompt: "FolderPassword",
            props: {requiredFolderPasswords: requiredFolderPasswordsCopy},

            confirm: confirm
          })
          console.log("closeHovercloseHovercloseHover")
        })

      }
    },
    forgotPassword() {
      store.commit("showHover", {
        prompt: "ResetFolderPassword",
        props: {folderId: this.folderId, lockFrom: this.lockFrom},

        confirm: () => {
          this.finishAndShowAnotherPrompt()

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
