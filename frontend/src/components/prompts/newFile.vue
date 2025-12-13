<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.newFile') }}</h2>
      </div>

      <div class="card-content">
         <p>{{ $t('prompts.newFileMessage') }}</p>
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
            id="create-button"
            :aria-label="$t('buttons.create')"
            :disabled="!canSubmit"
            :title="$t('buttons.create')"
            class="button button--flat"
            @click="submit"
         >
            {{ $t('buttons.create') }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'
import { detectExtension, onceAtATime } from "@/utils/common.js"
import { createFile } from "@/api/files.js"
import { v4 as uuidv4 } from "uuid"
import { generateIv, generateKey } from "@/upload/utils/uploadHelper.js"

export default {
   name: 'new-file',

   data() {
      return {
         name: ''
      }
   },

   props: {
      folder: {
         type: Object,
         required: false
      }
   },

   computed: {
      ...mapState(useMainStore, ['currentFolder', 'currentPrompt', 'settings']),
      canSubmit() {
         return this.name.length > 0
      }
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover']),

      submit: onceAtATime(async function () {
         if (this.canSubmit) {
            try {
               let folder = this.folder || this.currentFolder

               let encryptionMethod = this.settings.encryptionMethod
               let iv = generateIv(encryptionMethod)
               let key = generateKey(encryptionMethod)
               let file_data = {
                  "name": this.name,
                  "parent_id": folder.id,
                  "mimetype": "text/plain",
                  "extension": detectExtension(this.name),
                  "size": 0,
                  "frontend_id": uuidv4(),
                  "encryption_method": parseInt(encryptionMethod),
                  "iv": iv,
                  "key": key,
                  "crc": 0,
                  "attachments": [],
               }
               let res = await createFile({ files: [file_data]})
               let file = res[0]
               if (file.type === "Code" || file.type === "Text" || file.type === "Database") {
                  this.$router.push({ name: 'Editor', params: { fileId: file.file_id, lockFrom: file.lockFrom } })
               }
            } finally {
               this.closeHover()
            }
         }
      })
   }
}
</script>
