<template>
   <div class="card floating">
      <div class="card-content">
         <p v-if="selectedCount === 1">
            {{ $t("prompts.restoreFromTrashMessageSingle") }}
         </p>
         <p v-else-if="selectedCount > 1">
            {{ $t("prompts.restoreFromTrashMessageMultiple", { count: selectedCount }) }}
         </p>
      </div>
      <div class="card-action">
         <button
            :aria-label="$t('buttons.cancel')"
            :title="$t('buttons.cancel')"
            class="button button--flat button--grey"
            @click="closeHover()"
         >
            {{ $t("buttons.cancel") }}
         </button>
         <button
            :aria-label="$t('buttons.restoreFromTrash')"
            :title="$t('buttons.restoreFromTrash')"
            class="button button--flat button--red"
            @click="submit"
         >
            {{ $t("buttons.restoreFromTrash") }}
         </button>
      </div>
   </div>
</template>

<script>
import { restoreFromTrash } from "@/api/item.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { onceAtATime, buildResourcePasswords } from "@/utils/common.js"

export default {
   name: "RestoreFromTrash",

   computed: {
      ...mapState(useMainStore, ["selectedCount", "currentPrompt", "selected"])
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "resetSelected"]),

      submit: onceAtATime(async function() {
         const groups = new Map()
         for (const item of this.selected) {
            if (!groups.has(item.parent_id)) groups.set(item.parent_id, [])
            groups.get(item.parent_id).push(item)
         }

         for (const items of groups.values()) {
            const ids = items.map((item) => item.id)
            const resourcePasswords = buildResourcePasswords(items)
            const res = await restoreFromTrash({ ids, resourcePasswords })
            const message = this.$t("toasts.itemsAreBeingRestoredFromTrash", { amount: ids.length })
            this.$toast.info(message, {
               timeout: null,
               id: res.task_id
            })
         }

         if (this.currentPrompt.confirm) this.currentPrompt.confirm()

         this.closeHover()
         this.resetSelected()

      })
   }
}
</script>
