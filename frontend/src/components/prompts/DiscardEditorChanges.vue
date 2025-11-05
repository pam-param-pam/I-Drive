<template>
  <div class="card floating">
    <div class="card-content">
      <p>
        {{ $t("prompts.discardEditorChanges") }}
      </p>
    </div>
    <div class="card-action">
      <button
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
        class="button button--flat button--grey"
        tabindex="2"
        @click="closeHover()"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        id="focus-prompt"
        :aria-label="$t('buttons.discardChanges')"
        :title="$t('buttons.discardChanges')"
        class="button button--flat button--red"
        tabindex="1"
        @click="submit"
      >
        {{ $t("buttons.discardChanges") }}
      </button>
    </div>
  </div>
</template>

<script>
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"

export default {
   name: "DiscardEditorChanges",

   computed: {
      ...mapState(useMainStore, ["selected", "currentPrompt"]),
      file() {
         return this.selected[0]
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      async submit() {
         if (this.currentPrompt.confirm) this.currentPrompt.confirm()
         this.closeHover()
      }
   }
}
</script>
