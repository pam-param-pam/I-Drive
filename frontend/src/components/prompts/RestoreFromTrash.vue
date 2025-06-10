<template>
   <div class="card floating">
      <div class="card-content">
         <p v-if="selectedCount === 1">
            {{ $t('prompts.restoreFromTrashMessageSingle') }}
         </p>
         <p v-else-if="selectedCount > 1">
            {{ $t('prompts.restoreFromTrashMessageMultiple', { count: selectedCount }) }}
         </p>
      </div>
      <div class="card-action">
         <button
            :aria-label="$t('buttons.cancel')"
            :title="$t('buttons.cancel')"
            class="button button--flat button--grey"
            @click="closeHover()"
         >
            {{ $t('buttons.cancel') }}
         </button>
         <button
            :aria-label="$t('buttons.restoreFromTrash')"
            :title="$t('buttons.restoreFromTrash')"
            class="button button--flat button--red"
            @click="submit"
         >
            {{ $t('buttons.restoreFromTrash') }}
         </button>
      </div>
   </div>
</template>

<script>
import { restoreFromTrash } from '@/api/item.js'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { onceAtATime } from "@/utils/common.js"

export default {
   name: 'RestoreFromTrash',

   computed: {
      ...mapState(useMainStore, ['selectedCount', 'currentPrompt', 'selected', 'items'])
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'resetSelected', 'setItems']),

      submit: onceAtATime(async function () {

         let ids = this.selected.map((item) => item.id)

         let res = await restoreFromTrash({ ids: ids })

         let message = this.$t('toasts.itemsAreBeingRestoredFromTrash', { amount: ids.length })
         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })
         // let filteredItems = this.items.filter((item) => !ids.includes(item.id))
         // this.setItems(filteredItems)

         if (this.currentPrompt.confirm) this.currentPrompt.confirm()

         this.closeHover()
         this.resetSelected()

      })
   }
}
</script>
