<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.move') }}</h2>
      </div>

      <div class="card-content">
         <p>
            {{ $t('prompts.moveTo') }} <code class="move-to">{{ dest?.folder_path }}</code>
         </p>
         <FolderList ref="fileList" @update:current="(val) => (dest = val)"> </FolderList>
      </div>

      <div
         class="card-action"
         style="display: flex; align-items: center; justify-content: space-between"
      >
         <template v-if="perms.create">
            <button
               :aria-label="$t('sidebar.newFolder')"
               :title="$t('sidebar.newFolder')"
               class="button button--flat"
               style="justify-self: left"
               @click="createDir()"
            >
               <span>{{ $t('sidebar.newFolder') }}</span>
            </button>
         </template>
         <div>
            <button
               :aria-label="$t('buttons.cancel')"
               :title="$t('buttons.cancel')"
               class="button button--flat button--grey"
               @click="closeHover()"
            >
               {{ $t('buttons.cancel') }}
            </button>
            <button
               :aria-label="$t('buttons.move')"
               :disabled="isMoveDisabled"
               :title="$t('buttons.move')"
               class="button button--flat"
               @click="submit"
            >
               {{ $t('buttons.move') }}
            </button>
         </div>
      </div>
   </div>
</template>

<script>
import FolderList from '@/components/FolderList.vue'
import { move } from '@/api/item.js'
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'
import { onceAtATime } from "@/utils/common.js"

export default {
   name: 'move',

   components: { FolderList },

   data() {
      return {
         dest: null
      }
   },

   computed: {
      ...mapState(useMainStore, ['perms', 'selected']),

      isMoveDisabled() {
         return this.selected[0].parent_id === this.dest?.id
      }
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'addSelected', 'showHover', 'resetSelected']),

      createDir() {
         this.showHover({
            prompt: 'newFolder',
            props: { folder: this.dest },
            confirm: (data) => {
               this.$refs.fileList.dirs.push(data)
            }
         })
      },

      submit: onceAtATime(async function () {
         let ids = this.selected.map((obj) => obj.id)
         let res = await move({ ids: ids, new_parent_id: this.dest.id })

         let message = this.$t('toasts.movingItems')
         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })

         this.resetSelected()
         this.closeHover()
      })
   }
}
</script>
<style scoped>
.move-to {
   color: var(--textSecondary)
}
</style>