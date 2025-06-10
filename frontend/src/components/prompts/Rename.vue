<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.rename') }}</h2>
      </div>

      <div class="card-content">
         <p>
            {{ $t('prompts.renameMessage') }} <code>{{ oldName }}</code
            >:
         </p>
         <input v-focus v-model.trim="name" class="input input--block" type="text" />
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
            :aria-label="$t('buttons.rename')"
            :disabled="!canSubmit"
            :title="$t('buttons.rename')"
            class="button button--flat"
            type="submit"
            @click="submit()"
         >
            {{ $t('buttons.rename') }}
         </button>
      </div>
   </div>
</template>

<script>
import { rename } from '@/api/item.js'
import throttle from 'lodash.throttle'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { onceAtATime } from "@/utils/common.js"

export default {
   name: 'rename',

   data() {
      return {
         name: '',
         oldName: ''
      }
   },

   computed: {
      ...mapState(useMainStore, ['selected', 'currentPrompt']),
      canSubmit() {
         return this.name !== this.selected[0].name
      }
   },

   created() {
      this.name = this.selected[0].name
      this.oldName = this.name
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover']),

      submit: onceAtATime(async function () {
         if (this.canSubmit) {
            let id = this.selected[0].id
            let new_name = this.name
            await rename({ id: id, new_name: new_name })

            let message = this.$t('toasts.itemRenamed')
            this.$toast.success(message)

            if (this.currentPrompt.confirm) this.currentPrompt.confirm(new_name)

            this.closeHover()
         }
      })
   }
}
</script>
