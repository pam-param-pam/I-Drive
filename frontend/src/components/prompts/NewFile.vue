<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.newFile") }}</h2>
    </div>

    <div class="card-content">
      <p>{{ $t("prompts.newFileMessage") }}</p>
      <input
        class="input input--block"
        v-focus
        type="text"
        v-model.trim="name"
      />
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="closeHover()"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        class="button button--flat"
        @click="submit"
        :aria-label="$t('buttons.create')"
        :title="$t('buttons.create')"
      >
        {{ $t("buttons.create") }}
      </button>
    </div>
  </div>
</template>

<script>


import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"

export default {
   name: "new-file",
   data() {
      return {
         name: "",
      }
   },
   computed: {
      ...mapState(useMainStore, ["currentFolder"]),
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"]),
      async submit(event) {
         //todo
      },
   },
}
</script>
