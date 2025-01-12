<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.irreversibleAction") }}</h2>
    </div>
    <div class="card-content">
      <p v-if="selectedCount === 1">
        {{ $t("prompts.deleteMessageSingle") }}
      </p>
      <p v-else-if="selectedCount > 1">
        {{ $t("prompts.deleteMessageMultiple", {count: selectedCount}) }}
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
        :aria-label="$t('buttons.delete')"
        :title="$t('buttons.delete')"
      >
        {{ $t("buttons.delete") }}
      </button>

    </div>
  </div>
</template>

<script>
import {remove} from "@/api/item.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"


export default {
   name: "delete",
   computed: {
      ...mapState(useMainStore, ["selected", "items", "selectedCount", "currentPrompt"]),

   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "resetSelected", "setItems"]),
      async submit() {
         try {
            let ids = this.selected.map(item => item.id)
            let res = await remove({"ids": ids})

            let message = this.$t('toasts.itemsAreBeingDeleted', {amount: ids.length})
            this.$toast.info(message, {
               timeout: null,
               id: res.task_id,
            })

            let filteredItems = this.items.filter(item => !ids.includes(item.id));
            this.setItems(filteredItems)

            if (this.currentPrompt.confirm) this.currentPrompt.confirm()
            this.resetSelected()

         } finally {
            this.closeHover()
         }
      },

   },
}
</script>
