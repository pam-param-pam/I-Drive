<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.resetFolderPassword') }}</h2>
      </div>

      <div class="card-content">
         <p>{{ $t('prompts.resetMessage') }}:</p>

         <div>
            <input
               v-focus
               v-model.trim="accountPassword"
               :placeholder="$t('prompts.accountPassword')"
               class="input input--block styled-input"
            />
         </div>

         <div>
            <input
               v-model.trim="folderPassword"
               :placeholder="$t('prompts.newFolderPassword')"
               class="input input--block styled-input"
            />
         </div>

         <div class="checkbox-group">
            <label>
               <input v-model="pinkyPromise" type="checkbox" />
               {{ $t('prompts.pinkyPromiseResetFolderPassword') }}
            </label>
         </div>
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
            :aria-label="$t('buttons.reset')"
            :disabled="!pinkyPromise || accountPassword === ''"
            :title="$t('buttons.reset')"
            class="button button--flat"
            type="submit"
            @click="submit()"
         >
            {{ $t('buttons.reset') }}
         </button>
      </div>
   </div>
</template>

<script>
import { resetPassword } from '@/api/folder.js'
import throttle from 'lodash.throttle'
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'

export default {
   name: 'resetFolderPassword',

   props: {
      folderId: {
         type: String,
         required: true
      },
      lockFrom: {
         type: String,
         required: true
      }
   },

   data() {
      return {
         accountPassword: '',
         folderPassword: '',
         pinkyPromise: false
      }
   },

   computed: {
      ...mapState(useMainStore, ['currentPrompt', 'previousPromptName'])
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'setFolderPassword']),

      submit: throttle(async function (event) {
         let res = await resetPassword(this.folderId, this.accountPassword, this.folderPassword)
         let message = this.$t('toasts.passwordIsBeingUpdated')
         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })
         this.setFolderPassword({ folderId: this.folderId, password: this.folderPassword })

         if (this.previousPromptName === 'FolderPassword') {
            let confirmFunc = this.currentPrompt.confirm

            this.closeHover()
            if (confirmFunc) confirmFunc()
         } else {
            this.closeHover()
            this.currentPrompt.confirm()
         }
      }, 1000)
   }
}
</script>

<style scoped>
.checkbox-group {
   margin-bottom: 15px;
}
</style>
