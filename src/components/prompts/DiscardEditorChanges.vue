<template>
  <div class="card floating">
    <div class="card-content">
      <p>
        {{ $t("prompts.discardEditorChanges") }}
      </p>
    </div>
    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="$store.commit('closeHover')"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
        tabindex="2"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        id="focus-prompt"
        @click="submit"
        class="button button--flat button--red"
        :aria-label="$t('buttons.discardChanges')"
        :title="$t('buttons.discardChanges')"
        tabindex="1"
      >
        {{ $t("buttons.discardChanges") }}
      </button>
    </div>
  </div>
</template>

<script>
import {mapGetters, mapState} from "vuex"

export default {
  name: "DiscardEditorChanges",
  computed: {
    ...mapState(["selected"]),
    ...mapGetters(["currentPrompt"]),

    file() {
      return this.selected[0]
    }
  },
  methods: {
    submit: async function () {
      this.currentPrompt?.confirm()

    },
  },
}
</script>