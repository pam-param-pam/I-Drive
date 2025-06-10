<template>
   <div class="card floating">
      <div class="card-content">
         <p v-if="selectedCount === 1">
            {{ $t('prompts.moveToTrashMessageSingle') }}
         </p>
         <p v-else-if="selectedCount > 1">
            {{ $t('prompts.moveToTrashMessageMultiple', { count: selectedCount }) }}
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
            :aria-label="$t('buttons.moveToTrash')"
            :title="$t('buttons.moveToTrash')"
            class="button button--flat button--red"
            @click="submit"
         >
            {{ $t('buttons.moveToTrash') }}
         </button>
      </div>
   </div>
</template>

<script>
import { moveToTrash } from '@/api/item.js'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { onceAtATime } from "@/utils/common.js"

export default {
   name: 'MoveToTrash',

   computed: {
      ...mapState(useMainStore, ['selected', 'items', 'selectedCount', 'currentPrompt'])
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'resetSelected', 'setItems']),

      submit: onceAtATime(async function () {
         let ids = this.selected.map((item) => item.id)
         let res = await moveToTrash({ ids: ids })
         let message = this.$t('toasts.itemsAreBeingMovedToTrash', { amount: ids.length })

         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })

         // let filteredItems = this.items.filter((item) => !ids.includes(item.id))
         // this.setItems(filteredItems)

         if (this.currentPrompt.confirm) this.currentPrompt.confirm()

         this.resetSelected()
         this.closeHover()
      })
   }
}
</script>
