<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.editTags') }}</h2>
      </div>

      <div class="card-content">
         <p>
            {{ $t('prompts.editTagsDescription') }}
         </p>

         <div class="tags-container">
            <span v-for="(tag, index) in tags" :key="index" class="tag">
               <i class="material-icons tag-icon">sell</i>

               {{ tag }}
               <button
                  :aria-label="$t('buttons.removeTag', { tag })"
                  class="remove-tag-button"
                  @click="removeTag(tag)"
               >
                  <i class="material-icons close-icon">close</i>
               </button>
            </span>
         </div>

         <div class="tag-input-container">
            <input
               v-model="tagName"
               v-focus
               :placeholder="$t('prompts.enterTagName')"
               class="input input--block"
               type="text"
            />
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
            v-if="tagName !== ''"
            :aria-label="$t('buttons.addTag')"
            :title="$t('buttons.addTag')"
            class="button button--flat"
            type="submit"
            @click="submit()"
         >
            {{ $t('buttons.addTag') }}
         </button>
         <button
            v-else
            :aria-label="$t('buttons.ok')"
            :title="$t('buttons.ok')"
            class="button button--flat"
            type="submit"
            @click="submit()"
         >
            {{ $t('buttons.ok') }}
         </button>
      </div>
   </div>
</template>

<script>
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { addTag, getTags, removeTag } from "@/api/files.js"
import { onceAtATime } from "@/utils/common.js"

export default {
   name: 'EditTags',

   data() {
      return {
         tags: [],
         tagName: ''
      }
   },

   computed: {
      ...mapState(useMainStore, ['selected']),

      file() {
         return this.selected[0]
      }
   },

   watch: {
      tagName(newVal) {
         if (newVal.includes(' ')) {
            this.submit()
         }
      }
   },

   async created() {
     this.tags = await getTags(this.file.id)
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'resetSelected', 'updateItem']),

      submit: onceAtATime(async function () {
         if (this.tagName === '') {
            this.closeHover()
            return
         }
         let tagName = this.tagName.trim()
         this.tagName = ''

         await addTag(this.file.id, { tag_name: tagName })
         this.tags.push(tagName)
      }),

      removeTag: onceAtATime(async function (tagName) {
         await removeTag(this.file.id, { tag_name: tagName })

         this.tags = this.tags.filter((tag) => tag !== tagName)
      })
   }
}
</script>

<style scoped>
.tags-container {
   display: flex;
   flex-wrap: wrap;
   gap: 8px;
   margin-bottom: 16px;
}

.tag {
   display: inline-flex;
   align-items: center;
   padding-left: 10px;
   padding-bottom: 4px;
   padding-top: 4px;
   background-color: var(--background);
   border-radius: 16px;
   font-size: 14px;
}

.remove-tag-button {
   margin-left: 2px;
   margin-right: 2px;
   background: none;
   border: none;
   cursor: pointer;
   font-size: 16px;
   color: var(--color-text);
}

.remove-tag-button:hover {
   color: red;
}

.close-icon {
   font-size: 10px;
}

.remove-tag-button i {
   padding-bottom: 0;
   padding-top: 4px;
}

.tag-icon {
   font-size: 16px;
   margin-right: 6px;
}
</style>
