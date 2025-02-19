<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.searchTune') }}</h2>
      </div>

      <div class="card-content">
         <div v-if="!isExpanded">
            <div>
               <label>{{ $t('prompts.fileType') }}</label>
               <select v-model="fileType" class="input input--block styled-select">
                  <option value="all">{{ $t('prompts.all') }}</option>
                  <option v-for="type in fileTypes" :key="type" :value="type">{{ type }}</option>
               </select>
            </div>

            <div>
               <label>{{ $t('prompts.extension') }}</label>
               <input
                  v-focus
                  v-model.trim="extension"
                  :placeholder="$t('prompts.enterExtension')"
                  class="input input--block styled-input"
                  type="text"
               />
            </div>

            <div class="checkbox-group">
               <label>
                  <input v-model="includeFiles" type="checkbox" />
                  {{ $t('prompts.includeFiles') }}
               </label>
            </div>

            <div class="checkbox-group">
               <label>
                  <input v-model="includeFolders" type="checkbox" />
                  {{ $t('prompts.includeFolders') }}
               </label>
            </div>

            <div>
               <label>{{ $t('prompts.resultLimit') }}</label>
               <input
                  v-model.number="resultLimit"
                  :placeholder="$t('prompts.enterResultLimit')"
                  class="input input--block styled-input"
                  type="number"
               />
            </div>
            <!-- Order By Field -->
            <div>
               <label>{{ $t('prompts.orderBy') }}</label>
               <select v-model="orderBy" class="input input--block styled-select">
                  <option value="created_at">{{ $t('prompts.orderByCreatedAt') }}</option>
                  <option value="duration">{{ $t('prompts.orderByDuration') }}</option>
                  <option value="size">{{ $t('prompts.orderBySize') }}</option>
                  <option value="name">{{ $t('prompts.orderByName') }}</option>
               </select>
            </div>
            <div class="checkbox-group">
               <label>
                  <input v-model="ascending" type="checkbox" />
                  {{ $t('prompts.ascending') }}
               </label>
            </div>
            <div>
               <label>{{ $t('prompts.tags') }}</label>
               <input
                  v-model.trim="tags"
                  :placeholder="$t('prompts.enterTags')"
                  class="input input--block styled-input"
                  type="text"
               />
            </div>
         </div>
         <!-- Expandable section -->
         <div class="expandable-section">
            <div class="expandable-header" @click="isExpanded = !isExpanded">
               <strong>{{ $t('prompts.advanced') }}</strong>
               <i :class="{ expanded: isExpanded }" class="material-icons expand-icon">
                  keyboard_arrow_down
               </i>
            </div>

            <div v-if="isExpanded" class="expandable-content">
               <div>
                  <label>{{ $t('prompts.limitToFolders') }}</label>
                  <input
                     v-model="limitToFolders"
                     :placeholder="$t('prompts.enterLimitToFolders')"
                     class="input input--block styled-input"
                     type="text"
                  />
               </div>
               <div>
                  <label>{{ $t('prompts.excludeFolders') }}</label>
                  <input
                     v-model="excludeFolders"
                     :placeholder="$t('prompts.enterExcludeFolders')"
                     class="input input--block styled-input"
                     type="text"
                  />
               </div>
               <div>
                  <label>{{ $t('prompts.property') }}</label>
                  <input
                     v-model="property"
                     :placeholder="$t('prompts.enterProperty')"
                     class="input input--block styled-input"
                     type="text"
                  />
               </div>
               <div>
                  <label>{{ $t('prompts.range') }}</label>
                  <input
                     v-model="range"
                     :placeholder="$t('prompts.enterRange')"
                     class="input input--block styled-input"
                     type="text"
                  />
               </div>
            </div>
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
            :aria-label="$t('buttons.submit')"
            :title="$t('buttons.submit')"
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

export default {
   name: 'filterFiles',

   data() {
      return {
         isExpanded: false,
         fileType: null,
         extension: null,
         includeFiles: null,
         includeFolders: null,
         resultLimit: null,
         fileTypes: ['application', 'audio', 'document', 'image', 'video', 'text'],
         tags: null,
         orderBy: null,
         ascending: null,
         limitToFolders: null,
         excludeFolders: null,
         property: null,
         range: null
      }
   },

   computed: {
      ...mapState(useMainStore, ['searchFilters', 'currentPrompt'])
   },

   created() {
      this.fileType = this.searchFilters.type || 'all'
      this.extension = this.searchFilters.extension || null
      this.includeFiles = this.searchFilters.files
      this.includeFolders = this.searchFilters.folders
      this.resultLimit = this.searchFilters.resultLimit || 100
      this.tags = this.searchFilters.tags || ''
      this.orderBy = this.searchFilters.orderBy || 'size'
      this.ascending = this.searchFilters.ascending || false
      this.limitToFolders = this.searchFilters.limitToFolders || ''
      this.excludeFolders = this.searchFilters.excludeFolders || ''
      this.property = this.searchFilters.property || ''
      this.range = this.searchFilters.range || ''
   },

   methods: {
      ...mapActions(useMainStore, [
         'setSearchFilters',
         'setDisabledCreation',
         'resetSelected',
         'closeHover',
         'setSortingBy',
         'setSortByAsc',
         'setError',
         'setLoading'
      ]),

      submit() {
         this.setDisabledCreation(true)
         this.resetSelected()

         this.resultLimit = this.resultLimit || 1

         if (this.fileType === 'all') this.fileType = null

         let searchFilterDict = {
            files: this.includeFiles,
            folders: this.includeFolders,
            resultLimit: this.resultLimit,
            tags: this.tags,
            orderBy: this.orderBy,
            ascending: this.ascending,
            limitToFolders: this.limitToFolders,
            excludeFolders: this.excludeFolders,
            property: this.property,
            range: this.range
         }

         if (this.fileType !== null) searchFilterDict.type = this.fileType
         if (this.extension !== null) searchFilterDict.extension = this.extension

         this.setSearchFilters(searchFilterDict)
         try {
            this.currentPrompt.confirm()
         } finally {
            this.closeHover()
         }

         this.setSortByAsc(!this.ascending)
         this.setSortingBy(this.orderBy)
         this.setError(null)
         this.setLoading(true)
      }
   }
}
</script>

<style scoped>
.checkbox-group {
   margin-bottom: 15px;
}
</style>
