<template>
   <div class="card floating">
      <div class="card-content">
         <p>{{ $t('prompts.deleteMessageShare') }}</p>
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
            :aria-label="$t('buttons.delete')"
            :title="$t('buttons.delete')"
            class="button button--flat button--red"
            @click="submit"
         >
            {{ $t('buttons.delete') }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'

export default {
   name: 'share-delete',

   computed: {
      ...mapState(useMainStore, ['currentPrompt'])
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover']),

      submit() {
         if (this.currentPrompt.confirm) this.currentPrompt.confirm()
      }
   }
}
</script>
