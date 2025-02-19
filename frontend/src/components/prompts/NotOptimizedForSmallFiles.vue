<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.iDriveNotOptimized') }}</h2>
      </div>
      <div class="card-content">
         <p>
            {{ $t('prompts.iDriveNotOptimizedMessage') }}
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
            :aria-label="$t('buttons.delete')"
            :title="$t('buttons.delete')"
            class="button button--flat button--red"
            @click="submit"
         >
            {{ $t('buttons.proceedAnyway') }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'

export default {
   name: 'NotOptimizedForSmallFiles',

   computed: {
      ...mapState(useMainStore, ['currentPrompt'])
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover']),

      async submit() {
         if (this.currentPrompt.confirm) this.currentPrompt.confirm()
         this.closeHover()
      }
   }
}
</script>
