<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.setFolderPassword") }}</h2>
    </div>

    <div class="card-content">
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
      <div v-if="locked">
        <p>
          {{ $t("prompts.enterOldFolderPassword") }}
        </p>
        <input
          class="input input--block"
          v-focus
          type="text"
          @keyup.enter="submit()"
          v-model.trim="password"
        />
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
        :aria-label="$t('buttons.submit')"
        :title="$t('buttons.submit')"
      >
        {{ $t("buttons.submit") }}
      </button>
    </div>
  </div>
</template>

<script>
import {mapGetters, mapMutations, mapState} from "vuex";
import {isPasswordCorrect} from "@/api/folder.js";

export default {
  name: "folder-password",
  data: function () {
    return {
      password: "",
    };
  },
  props: {
    folder_id: String
  },
  computed: {
    ...mapGetters(["currentPrompt"]),
    ...mapState(["selected"]),
    locked() {
      return this.selected[0].locked
    }
  },

  methods: {
    ...mapMutations(["closeHover", "setFolderPassword"]),

    submit: async function () {
      //todo
      /*
      if (await isPasswordCorrect(this.folder_id, this.password) === true) {
        this.setFolderPassword({"folderId": this.folder_id, "password": this.password})
        this.currentPrompt.confirm();
        this.closeHover()
      }
      else {
        let message = this.$t('toasts.folderPasswordIncorrect')
        this.$toast.info(message);
      }



       */


    },
  },
};
</script>
