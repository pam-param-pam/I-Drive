<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t("prompts.skipOnboardingTitle") }}</h2>
      </div>
      <div class="card-content">
         <p>
            {{ $t("prompts.skipOnboardingMessage") }}
         </p>
      </div>
      <div class="card-action">
         <button
            :aria-label="$t('buttons.cancel')"
            :title="$t('buttons.cancel')"
            class="button button--flat button--grey"
            @click="cancel"
         >
            {{ $t("buttons.cancel") }}
         </button>

         <button
            :aria-label="$t('buttons.confirm')"
            :title="$t('buttons.confirm')"
            class="button button--flat button--orange"
            @click="submit"
         >
            {{ $t("buttons.confirm") }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "SkipOnboarding.vue",

   computed: {
      ...mapState(useMainStore, ["currentPrompt"])
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      submit() {
         if (this.currentPrompt.confirm) this.currentPrompt.confirm()
         this.closeHover()
      },
      cancel() {
         if (this.currentPrompt.cancel) this.currentPrompt.cancel()
         this.closeHover()
      }
   }
}
</script>