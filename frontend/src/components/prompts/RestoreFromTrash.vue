<template>
  <div class="card floating">
    <div class="card-content">
      <p v-if="selectedCount === 1">
        {{ $t("prompts.restoreFromTrashMessageSingle") }}
      </p>
      <p v-else-if="selectedCount > 1">
        {{ $t("prompts.restoreFromTrashMessageMultiple", {count: selectedCount}) }}
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
        :aria-label="$t('buttons.restoreFromTrash')"
        :title="$t('buttons.restoreFromTrash')"
      >
        {{ $t("buttons.restoreFromTrash") }}
      </button>

    </div>
  </div>
</template>

<script>
import {restoreFromTrash} from "@/api/item.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"

export default {
   name: "RestoreFromTrash",
   computed: {
      ...mapState(useMainStore, ["selectedCount", "currentPrompt", "selected", "items"]),
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "resetSelected"]),
      async submit() {
         try {
            let ids = this.selected.map(item => item.id)

            let res = await restoreFromTrash({"ids": ids})
            if (res.status !== 204) {
               res = await res.data
               let message = this.$t('toasts.itemsAreBeingRestoredFromTrash', {amount: ids.length})
               this.$toast.info(message, {
                  timeout: null,
                  id: res.task_id
               })
            } else {
               let message = this.$t('toasts.itemsRestoredFromTrash', {amount: ids.length})

               this.$toast.success(message)
            }

            this.currentPrompt?.confirm()

         } finally {
            this.closeHover()
            this.resetSelected()

         }
      },
   },
}
</script>
