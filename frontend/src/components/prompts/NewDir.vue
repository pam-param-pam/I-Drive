<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.newDir") }}</h2>
    </div>

    <div class="card-content">
      <p>{{ $t("prompts.newDirMessage") }}</p>
      <input
        v-focus
        class="input input--block"
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
        :disabled="!canSubmit"
        :aria-label="$t('buttons.create')"
        id="create-button"
        :title="$t('buttons.create')"
        @click="submit"
      >
        {{ $t("buttons.create") }}
      </button>
    </div>
  </div>
</template>

<script>
import {create} from "@/api/folder.js"
import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"

export default {
   name: "new-dir",
   data() {
      return {
         name: "",
      }
   },
   props: {
      folder: {
         type: Object,
         required: false,
      },
   },
   computed: {
      ...mapState(useMainStore, ["currentFolder", "currentPrompt"]),
      canSubmit() {
         return this.name.length > 0
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),
      async submit(event) {
         if (this.canSubmit) {
            try {
               let folder = this.folder || this.currentFolder
               let res = await create({"parent_id": folder.id, "name": this.name})
               let message = this.$t('toasts.folderCreated', {name: this.name})
               this.$toast.success(message)
               if (this.currentPrompt.confirm) this.currentPrompt.confirm(res)
            } finally {
               this.closeHover()
            }
         }
      },
   },
}
</script>
