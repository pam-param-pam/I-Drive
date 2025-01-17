<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.uploadDestination") }}</h2>
    </div>
    <div class="card-content">
      <p>
        {{ $t("prompts.uploadDestinationWarning") }}
      </p>


    </div>
    <div class="card-action">
      <button
        @click="closeHover()"
        class="button button--flat button--grey"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        @click="submit"
        class="button button--flat button--red"
        :aria-label="$t('buttons.imSure')"
        :title="$t('buttons.imSure')"
      >
        {{ $t("buttons.imSure") }}
      </button>

    </div>
  </div>
</template>

<script>

import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"

export default {
   name: "UploadDestinationWarning",
   computed: {
      ...mapState(useMainStore, ["currentPrompt"]),
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      async submit() {

         if (this.currentPrompt.confirm) this.currentPrompt.confirm()
         this.closeHover()

      },
   },
}
</script>
