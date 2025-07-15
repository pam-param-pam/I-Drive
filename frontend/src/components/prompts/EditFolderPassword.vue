<template>
   <div class="card floating">
      <div class="card-title">
         <h2 v-if="!isLocked">{{ $t('prompts.setFolderPassword') }}</h2>
         <h2 v-if="isLocked">{{ $t('prompts.editFolderPassword') }}</h2>
      </div>

      <div class="card-content">
         <p v-if="isLocked">
            {{ $t('prompts.enterOldFolderPassword') }}
         </p>
         <input
            v-if="isLocked"
            v-focus
            v-model.trim="oldPassword"
            class="input input--block"
            type="text"
         />
         <p>
            {{ $t('prompts.enterNewFolderPassword') }}
         </p>
         <input v-focus v-model.trim="password" class="input input--block" type="text" />
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
            :aria-label="$t('buttons.submit')"
            :title="$t('buttons.submit')"
            class="button button--flat"
            type="submit"
            @click="submit()"
         >
            {{ $t('buttons.submit') }}
         </button>
      </div>
   </div>
</template>

<script>
import { lockWithPassword } from '@/api/folder.js'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { onceAtATime } from "@/utils/common.js"

export default {
   name: 'folder-password',

   data() {
      return {
         password: '',
         oldPassword: ''
      }
   },

   computed: {
      ...mapState(useMainStore, ['selected']),

      isLocked() {
         return this.selected[0].isLocked
      },
      folder_id() {
         return this.selected[0].id
      }
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'setFolderPassword']),

      submit: onceAtATime(async function () {
         if (!(this.password === '' && this.oldPassword === '')) {
            let res = await lockWithPassword(this.folder_id, this.password, this.oldPassword)
            let message = this.$t('toasts.passwordIsBeingUpdated')
            this.$toast.info(message, {
               timeout: null,
               id: res.task_id
            })
            this.closeHover()
         }
      })
   }
}
</script>
