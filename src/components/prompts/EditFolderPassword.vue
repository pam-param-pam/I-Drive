<template>
  <div class="card floating">
    <div class="card-title">
      <h2 v-if="!isLocked">{{ $t("prompts.setFolderPassword") }}</h2>
      <h2 v-if="isLocked">{{ $t("prompts.editFolderPassword") }}</h2>

    </div>

    <div class="card-content">

      <p v-if="isLocked">
        {{ $t("prompts.enterOldFolderPassword") }}
      </p>
      <input
        v-if="isLocked"
        class="input input--block"
        v-focus
        type="text"
        @keyup.enter="submit()"
        v-model.trim="oldPassword"
        />
      <p>
        {{ $t("prompts.enterNewFolderPassword") }}
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
        :aria-label="$t('buttons.submit')"
        :title="$t('buttons.submit')"
      >
        {{ $t("buttons.submit") }}
      </button>
    </div>
  </div>
</template>

<script>
import {mapGetters, mapMutations, mapState} from "vuex"
import {lockWithPassword} from "@/api/folder.js"

export default {
  name: "folder-password",
  data() {
    return {
      password: "",
      oldPassword: "",
    }
  },

  computed: {
    ...mapGetters(["currentPrompt"]),
    ...mapState(["selected"]),
    isLocked() {
      return this.selected[0].isLocked
    },
    folder_id(){
      return this.selected[0].id

    }
  },

  methods: {
    ...mapMutations(["closeHover", "setFolderPassword"]),

    submit: async function () {
      if (!(this.password === "" && this.oldPassword === "")) {
        try {
          let res = await lockWithPassword(this.folder_id, this.password, this.oldPassword)
          let message = this.$t('toasts.passwordIsBeingUpdated')
          this.$toast.info(message, {
            timeout: null,
            id: res.task_id,
          })
          this.$store.commit("closeHover")

        }
    catch
      (error)
      {
        console.log(error)
      }
    }
    },
  },
}
</script>
