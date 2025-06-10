<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.unlockFolder') }}</h2>
      </div>

      <div class="card-content">
         <p>
            {{ $t('prompts.enterFolderPassword') }} <code>{{ folder.name }}</code>
         </p>
         <input v-focus v-model.trim="password" class="input input--block" type="text" />
         <button
            :aria-label="$t('buttons.forgotFolderPassword')"
            :title="$t('buttons.forgotFolderPassword')"
            class="button button--small button--text-blue"
            @click="forgotPassword()"
         >
            {{ $t('buttons.forgotFolderPassword') }}
         </button>
      </div>

      <div class="card-action">
         <button
            :aria-label="$t('buttons.cancel')"
            :title="$t('buttons.cancel')"
            class="button button--flat button--grey"
            @click="cancel()"
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
            {{ $t('buttons.unlock') }}
         </button>
      </div>
   </div>
</template>

<script>
import throttle from 'lodash.throttle'
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'
import { isPasswordCorrect } from '@/api/resource.js'

export default {
   name: 'folder-password',

   data() {
      return {
         password: ''
      }
   },

   props: {
      requiredFolderPasswords: {
         type: Array,
         default: () => []
      }
   },

   computed: {
      ...mapState(useMainStore, ['loading', 'currentPrompt']),
      folder() {
         return this.requiredFolderPasswords[0]
      }
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'setFolderPassword', 'setError', 'showHover']),

      submit: throttle(async function (event) {
         if ((await isPasswordCorrect(this.folder.id, this.password)) === true) {
            this.setFolderPassword({ folderId: this.folder.id, password: this.password })

            this.finishAndShowAnotherPrompt()
         } else {
            let message = this.$t('toasts.folderPasswordIncorrect')
            this.$toast.error(message)
         }
      }, 1000),

      cancel() {
         this.$toast.error(this.$t('toasts.passwordIsRequired'))

         // Call the callback supplied during showHover()
         if (this.currentPrompt && typeof this.currentPrompt.cancel === "function") {
            this.currentPrompt.cancel()
         }

         this.closeHover()
      },

      finishAndShowAnotherPrompt() {
         let requiredFolderPasswordsCopy = [...this.requiredFolderPasswords]
         requiredFolderPasswordsCopy.shift()

         if (requiredFolderPasswordsCopy.length === 0) {
            let confirmFunc = this.currentPrompt.confirm
            this.closeHover()
            if (confirmFunc) confirmFunc()
         } else {
            console.log('showHovershowHovershowHover')
            let confirm = this.currentPrompt.confirm
            this.closeHover()
            this.$nextTick(() => {
               this.showHover({
                  prompt: 'FolderPassword',
                  props: { requiredFolderPasswords: requiredFolderPasswordsCopy },
                  confirm: confirm
               })
            })
         }
      },

      onPasswordReset() {
         this.finishAndShowAnotherPrompt()
      },

      forgotPassword() {
         this.showHover({
            prompt: 'ResetFolderPassword',
            props: { folderId: this.folder.id, lockFrom: this.folder.lockFrom },

            confirm: () => {
               this.onPasswordReset()
            }
         })
      }
   }
}
</script>

<style scoped>
.button--small {
   font-size: 0.875rem;
   padding: 0.5rem 1rem;
   border: none;
   background: none;
   color: #3a96f6;
}

.button--small:hover {
   text-decoration: underline;
   background: none;
}
</style>
