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
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="cancelBtn()"
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

export default {
  name: "folder-password",
  data: function () {
    return {
      password: "",
    }
  },
  props: {
    folderId: String,
    lockFrom: String,
  },
  computed: {
    ...mapGetters(["currentPrompt", "getFolderPassword"]),
    ...mapState(["selected"]),

  },

  methods: {
    ...mapMutations(["closeHover", "setFolderPassword"]),

    async submit() {

      if (await isPasswordCorrect(this.folderId, this.password) === true) {
        this.setFolderPassword({"folderId": this.lockFrom, "password": this.password})
        this.currentPrompt.confirm()
        this.closeHover()
      }
      else {
        let message = this.$t('toasts.folderPasswordIncorrect')
        this.$toast.error(message)
      }

    },
    cancelBtn() {
      if (this.currentPrompt.cancel) this.currentPrompt.cancel()

      this.closeHover()

    }
  },
}
</script>
