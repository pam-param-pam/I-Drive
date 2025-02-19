<template>
   <div class="card floating help">
      <div class="card-title">
         <h2>{{ $t('help.help') }}</h2>
      </div>

      <div class="card-content">
         <ul>
            <li><strong>F1</strong> - {{ $t('help.f1') }}</li>
            <li><strong>F2</strong> - {{ $t('help.f2') }}</li>
            <li><strong>DEL</strong> - {{ $t('help.del') }}</li>
            <li><strong>ESC</strong> - {{ $t('help.esc') }}</li>
            <li><strong>CTRL + S</strong> - {{ $t('help.ctrl.s') }}</li>
            <li><strong>Click</strong> - {{ $t('help.click') }}</li>
            <li><strong>Double click</strong> - {{ $t('help.doubleClick') }}</li>
         </ul>
      </div>

      <div class="card-action">
         <button
            :aria-label="$t('buttons.ok')"
            :title="$t('buttons.ok')"
            class="button button--flat"
            type="submit"
            @click="closeHover()"
         >
            {{ $t('buttons.ok') }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'

export default {
   name: 'help',

   methods: {
      ...mapActions(useMainStore, ['closeHover'])
   }
}
</script>
