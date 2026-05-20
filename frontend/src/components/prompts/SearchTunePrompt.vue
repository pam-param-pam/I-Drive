<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t("prompts.searchTune") }}</h2>
      </div>

      <div class="card-content">
         <div v-if="!isExpanded">
            <div>
               <label>{{ $t("prompts.fileType") }}</label>
               <select v-model="fileType" class="input input--block styled-select">
                  <option value="All">{{ $t("prompts.all") }}</option>
                  <option v-for="type in fileTypes" :key="type" :value="type">{{ type }}</option>
               </select>
            </div>

            <div>
               <label>{{ $t("prompts.extension") }}</label>
               <div class="tags-container">
                  <span v-for="ext in selectedExtensions" :key="ext" class="tag">
                     {{ ext }}
                     <button class="remove-tag-button" @click="removeExtension(ext)">
                        <i class="material-icons close-icon">close</i>
                     </button>
                  </span>
               </div>
               <input
                 v-model="extensionQuery"
                 class="input input--block"
                 :placeholder="$t('prompts.enterExtension')"
                 @input="searchExtensions"
                 @focus="searchExtensions"
                 @blur="clearSuggestions('extensionSuggestions')"
               />
               <Transition name="fade">
                  <div v-if="extensionSuggestions.length" class="suggestions">
                     <div
                       v-for="ext in extensionSuggestions"
                       :key="ext"
                       class="suggestion"
                       @mousedown.prevent
                       @click="addExtension(ext)"
                     >
                        {{ ext }}
                     </div>
                  </div>
               </Transition>
            </div>

            <div class="checkbox-group">
               <label>
                  <input v-model="includeFiles" type="checkbox" />
                  {{ $t("prompts.includeFiles") }}
               </label>
            </div>
            <div class="checkbox-group">
               <label>
                  <input
                    v-model="includeFolders"
                    type="checkbox"
                    :disabled="fileSpecificFiltersPresent"
                  />
                  {{ $t("prompts.includeFolders") }}
               </label>
            </div>

            <div>
               <label>{{ $t("prompts.resultLimit") }}</label>
               <input
                 v-model.number="resultLimit"
                 class="input input--block styled-input"
                 type="number"
               />
            </div>

            <div>
               <label>{{ $t("prompts.orderBy") }}</label>
               <select v-model="orderBy" class="input input--block styled-select">
                  <option value="created_at">{{ $t("prompts.orderByCreatedAt") }}</option>
                  <option value="size">{{ $t("prompts.orderBySize") }}</option>
                  <option value="name">{{ $t("prompts.orderByName") }}</option>
               </select>
            </div>
            <div class="checkbox-group">
               <label>
                  <input v-model="ascending" type="checkbox" />
                  {{ $t("prompts.ascending") }}
               </label>
            </div>
         </div>

         <div class="expandable-section">
            <div class="expandable-header" @click="isExpanded = !isExpanded">
               <strong>{{ $t("prompts.advanced") }}</strong>
               <i :class="{ expanded: isExpanded }" class="material-icons expand-icon"> keyboard_arrow_down </i>
            </div>
            <div v-if="isExpanded" class="expandable-content">
               <div>
                  <label>{{ $t("prompts.tags") }}</label>
                  <div class="tags-container">
                     <span v-for="tag in selectedTags" :key="tag.id" class="tag">
                        <i class="material-icons tag-icon">sell</i>
                        {{ tag.name }}
                        <button class="remove-tag-button" @click="removeSelectedTag(tag)">
                           <i class="material-icons close-icon">close</i>
                        </button>
                     </span>
                  </div>
                  <input
                    v-model="tagQueryInclude"
                    class="input input--block"
                    placeholder="Search tags..."
                    @input="searchTags"
                    @focus="searchTags"
                    @blur="clearSuggestions('tagSuggestionsInclude')"
                  />
                  <Transition name="fade">
                     <div v-if="tagSuggestionsInclude.length" class="suggestions">
                        <div
                          v-for="tag in tagSuggestionsInclude"
                          :key="tag.id"
                          class="suggestion"
                          @mousedown.prevent
                          @click="addSelectedTag(tag)"
                        >
                           {{ tag.name }}
                        </div>
                     </div>
                  </Transition>
               </div>

               <div>
                  <label>{{ $t("prompts.limitToFolders") }}</label>
                  <div class="tags-container">
                     <span v-for="f in limitToFolders" :key="f.id" class="tag">
                        <i class="material-icons tag-icon">folder</i>
                        {{ f.name }}
                        <button class="remove-tag-button" @click="removeLimitFolder(f)">
                           <i class="material-icons close-icon">close</i>
                        </button>
                     </span>
                  </div>
                  <input
                    v-model="folderQueryLimit"
                    class="input input--block"
                    placeholder="Search folders..."
                    @input="searchFolders('limit')"
                    @focus="searchFolders('limit')"
                    @blur="clearSuggestions('folderSuggestionsLimit')"
                  />
                  <Transition name="fade">
                     <div v-if="folderSuggestionsLimit.length" class="suggestions">
                        <div
                          v-for="f in folderSuggestionsLimit"
                          :key="f.id"
                          class="suggestion"
                          @mousedown.prevent
                          @click="addLimitFolder(f)"
                        >
                           {{ f.name }}
                        </div>
                     </div>
                  </Transition>
               </div>

               <div>
                  <label>{{ $t("prompts.excludeFolders") }}</label>
                  <div class="tags-container">
                     <span v-for="f in excludeFolders" :key="f.id" class="tag">
                        <i class="material-icons tag-icon">folder</i>
                        {{ f.name }}
                        <button class="remove-tag-button" @click="removeExcludeFolder(f)">
                           <i class="material-icons close-icon">close</i>
                        </button>
                     </span>
                  </div>
                  <input
                    v-model="folderQueryExclude"
                    class="input input--block"
                    placeholder="Search folders..."
                    @input="searchFolders('exclude')"
                    @focus="searchFolders('exclude')"
                    @blur="clearSuggestions('folderSuggestionsExclude')"
                  />
                  <Transition name="fade">
                     <div v-if="folderSuggestionsExclude.length" class="suggestions">
                        <div
                          v-for="f in folderSuggestionsExclude"
                          :key="f.id"
                          class="suggestion"
                          @mousedown.prevent
                          @click="addExcludeFolder(f)"
                        >
                           {{ f.name }}
                        </div>
                     </div>
                  </Transition>
               </div>

               <div>
                  <label>{{ $t("prompts.property") }}</label>
                  <select
                    v-model="property"
                    class="input input--block styled-input"
                    @change="onPropertyChange"
                  >
                     <option value="">{{ $t("prompts.selectProperty") }}</option>
                     <option v-for="prop in properties" :key="prop.value" :value="prop.value">
                        {{ prop.label }}
                     </option>
                  </select>
               </div>
               <div v-if="selectedPropertyType">
                  <label>{{ $t("prompts.propertyValue") }}</label>
                  <input
                    v-if="selectedPropertyType === 'string'"
                    v-model="range.value"
                    class="input input--block styled-input"
                    placeholder="Regex"
                  />
                  <div v-if="selectedPropertyType === 'number'" class="range-group">
                     <select v-model="range.mode" class="input range-mode">
                        <option value="between">Between</option>
                        <option value="before">Less than</option>
                        <option value="after">Greater than</option>
                     </select>
                     <div class="range-inputs">
                        <input
                          v-if="range.mode !== 'before'"
                          v-model.number="range.from"
                          class="input"
                          type="number"
                          :placeholder="placeholderFrom"
                        />
                        <input
                          v-if="range.mode !== 'after'"
                          v-model.number="range.to"
                          class="input"
                          type="number"
                          :placeholder="placeholderTo"
                        />
                     </div>
                  </div>
                  <div v-if="selectedPropertyType === 'date'" class="range-group">
                     <select v-model="range.mode" class="input range-mode">
                        <option value="between">Between</option>
                        <option value="before">Before</option>
                        <option value="after">After</option>
                     </select>
                     <div class="range-inputs">
                        <input
                          v-if="range.mode !== 'before'"
                          v-model="range.from"
                          class="input"
                          type="date"
                        />
                        <input
                          v-if="range.mode !== 'after'"
                          v-model="range.to"
                          class="input"
                          type="date"
                        />
                     </div>
                  </div>
               </div>
            </div>
         </div>
      </div>

      <div class="card-action">
         <button class="button button--flat button--grey" @click="cancel()">
            {{ $t("buttons.cancel") }}
         </button>
         <button class="button button--flat button--red" @click="clearAll">
            {{ $t("buttons.clearAll") }}
         </button>
         <button class="button button--flat" @click="submit()">
            {{ $t("buttons.ok") }}
         </button>
      </div>
   </div>
</template>

<script>
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { onceAtATime } from "@/utils/common.js"
import { search } from "@/api/search.js"
import { getTags } from "@/api/user.js"

export default {
   name: "filterFiles",

   data() {
      return {
         isExpanded: false,

         // Basic
         fileType: "",
         extensionQuery: "",
         includeFiles: undefined,
         includeFolders: undefined,
         resultLimit: 0,
         orderBy: "",
         ascending: undefined,

         selectedExtensions: [],
         extensionSuggestions: [],

         // Advanced – folders
         limitToFolders: [],
         excludeFolders: [],
         folderQueryLimit: "",
         folderQueryExclude: "",
         folderSuggestionsLimit: [],
         folderSuggestionsExclude: [],

         // Advanced – tags
         selectedTags: [],
         tagQueryInclude: "",
         tagSuggestionsInclude: [],

         // Property filter
         property: null,
         range: { from: null, to: null, value: null, mode: "between" },

         properties: [
            { label: "Name", value: "name", type: "string" },
            { label: "Extension", value: "extension", type: "string" },
            { label: "Size", value: "size", type: "number" },
            { label: "Created At", value: "created_at", type: "date" },
            { label: "Last Modified At", value: "last_modified_at", type: "date" }
         ],

         previousIncludeFolders: null
      }
   },

   created() {
      this.initState()
   },

   computed: {
      ...mapState(useMainStore, ["searchFilters", "currentPrompt", "config", "currentFolder"]),

      fileTypes() {
         const map = this.config.extensions || {}
         return [...new Set(Object.values(map))].sort()
      },

      allExtensions() {
         const map = this.config.extensions || {}
         if (this.fileType === "All") {
            return Object.keys(map)
         }
         return Object.entries(map)
           .filter(([, type]) => type === this.fileType)
           .map(([ext]) => ext)
      },

      selectedPropertyType() {
         return this.properties.find((p) => p.value === this.property)?.type
      },

      computedFilter() {
         if (!this.property) return null
         if (this.selectedPropertyType === "string") {
            return { field: this.property, op: "regex", value: this.range.value }
         }
         if (this.selectedPropertyType === "number" || this.selectedPropertyType === "date") {
            if (this.range.mode === "between") {
               if (this.range.from == null || this.range.to == null) return null
               return {
                  field: this.property,
                  op: "between",
                  value: { from: this.range.from, to: this.range.to }
               }
            }
            if (this.range.mode === "before") return { field: this.property, op: "lt", value: this.range.to }
            if (this.range.mode === "after")  return { field: this.property, op: "gt", value: this.range.from }
         }
         return null
      },

      isFilterComplete() {
         const f = this.computedFilter
         if (!f) return false
         if (this.selectedPropertyType === "string") {
            return !!f.value
         }
         if (this.range.mode === "between") {
            return this.range.from != null && this.range.to != null
         }
         if (this.range.mode === "before") {
            return this.range.to != null
         }
         if (this.range.mode === "after") {
            return this.range.from != null
         }
         return false
      },

      fileSpecificFiltersPresent() {
         if (this.selectedExtensions.length > 0) return true
         if (this.selectedTags.length > 0) return true
         if (this.fileType !== "All") return true
         if (this.property && this.isFilterComplete) {
            const fileOnlyFields = ["size", "duration", "extension"]
            if (fileOnlyFields.includes(this.property)) return true
         }
         return false
      },

      placeholderFrom() {
         if (this.range.mode === "between") return this.$t("prompts.min")
         if (this.range.mode === "after")   return this.$t("prompts.greaterThan")
         return ""
      },

      placeholderTo() {
         if (this.range.mode === "between") return this.$t("prompts.max")
         if (this.range.mode === "before")  return this.$t("prompts.lessThan")
         return ""
      }
   },

   watch: {
      fileType(newType) {
         if (newType === "All") return
         this.selectedExtensions = this.selectedExtensions.filter(ext => {
            const typeOfExt = (this.config.extensions || {})[ext]
            return typeOfExt === newType
         })
      },

      // Disable folders when file‑specific filters appear, re‑enable when cleared
      fileSpecificFiltersPresent: {
         handler(newVal, oldVal) {
            if (newVal && !oldVal) {
               if (this.previousIncludeFolders === null) {
                  this.previousIncludeFolders = this.includeFolders
               }
               if (this.includeFolders) {
                  this.includeFolders = false
                  this.$toast.warning(this.$t("toasts.foldersDisabledFileFilters"))
               }
            } else if (!newVal && oldVal && this.previousIncludeFolders !== null) {
               this.includeFolders = this.previousIncludeFolders
               this.previousIncludeFolders = null
            }
         },
         immediate: false
      }
   },

   methods: {
      ...mapActions(useMainStore, ["setSearchFilters", "closeHover", "getFolderPassword", "resetSearchFilters"]),

      initState() {
         const internal = this.searchFilters.internal

         this.includeFiles = internal.files
         this.includeFolders = internal.folders
         this.resultLimit = internal.resultLimit
         this.orderBy = internal.orderBy
         this.ascending = internal.ascending
         this.fileType = internal.type
         this.selectedExtensions = internal.extensions ?? []
         this.selectedTags = internal.tags ?? []
         this.limitToFolders = internal.limitToFolders ?? []
         this.excludeFolders = internal.excludeFolders ?? []

         const f = internal.filter
         if (f) {
            this.property = f.field || ""
            if (f.op === "regex") this.range.value = f.value
            if (f.op === "between") {
               this.range.mode = "between"
               this.range.from = f.value?.from
               this.range.to = f.value?.to
            }
            if (f.op === "lt") {
               this.range.mode = "before"
               this.range.to = f.value
            }
            if (f.op === "gt") {
               this.range.mode = "after"
               this.range.from = f.value
            }
         } else {
            this.property = ""
            this.range = { from: null, to: null, value: null, mode: "between" }
         }

         this.previousIncludeFolders = null
      },

      clearSuggestions(field) {
         this[field] = []
      },

      saveCurrentStateToStore() {
         const internalState = {
            files: this.includeFiles,
            folders: this.includeFolders,
            resultLimit: this.resultLimit,
            orderBy: this.orderBy,
            ascending: this.ascending,
            type: this.fileType,
            extensions: [...this.selectedExtensions],
            tags: [...this.selectedTags],
            limitToFolders: [...this.limitToFolders],
            excludeFolders: [...this.excludeFolders],
            filter: this.isFilterComplete ? this.computedFilter : null,
         }

         const externalState = {
            files: this.includeFiles,
            folders: this.includeFolders,
            resultLimit: this.resultLimit,
            orderBy: this.orderBy,
            ascending: this.ascending,
            type: this.fileType !== "All" ? this.fileType : undefined,
            extensions: [...this.selectedExtensions],
            tags: this.selectedTags.map(t => t.id),
            limitToFolders: this.limitToFolders.map(f => f.id),
            excludeFolders: this.excludeFolders.map(f => f.id),
            filter: this.isFilterComplete ? this.computedFilter : null,
         }

         this.setSearchFilters({
            internal: internalState,
            external: externalState
         })
      },

      cancel() {
         this.saveCurrentStateToStore()
         this.closeHover()
      },

      clearAll() {
         this.resetSearchFilters()
         this.initState()
         this.$toast.success(this.$t("toasts.filtersCleared"))
      },

      async searchFolders(type) {
         const query = type === "limit" ? this.folderQueryLimit : this.folderQueryExclude
         const lockFrom = this.currentFolder?.lockFrom
         const password = this.getFolderPassword(lockFrom)
         const res = await search(
           { query: query || "", files: false, folders: true, resultLimit: 10 },
           lockFrom,
           password
         )
         const alreadySelected = type === "limit" ? this.limitToFolders : this.excludeFolders
         const filtered = res.filter(f => !alreadySelected.some(x => x.id === f.id))
         if (type === "limit") this.folderSuggestionsLimit = filtered
         else this.folderSuggestionsExclude = filtered
      },

      addLimitFolder(folder) {
         this.excludeFolders = this.excludeFolders.filter(x => x.id !== folder.id)
         if (!this.limitToFolders.find(x => x.id === folder.id)) {
            this.limitToFolders.push(folder)
         }
         this.folderQueryLimit = ""
         this.folderSuggestionsLimit = []
         this.searchFolders('limit')
      },

      addExcludeFolder(folder) {
         this.limitToFolders = this.limitToFolders.filter(x => x.id !== folder.id)
         if (!this.excludeFolders.find(x => x.id === folder.id)) {
            this.excludeFolders.push(folder)
         }
         this.folderQueryExclude = ""
         this.folderSuggestionsExclude = []
         this.searchFolders('exclude')
      },

      removeLimitFolder(folder) {
         this.limitToFolders = this.limitToFolders.filter(x => x.id !== folder.id)
      },

      removeExcludeFolder(folder) {
         this.excludeFolders = this.excludeFolders.filter(x => x.id !== folder.id)
      },

      async searchTags() {
         const query = this.tagQueryInclude.trim().toLowerCase()
         const tags = await getTags()
         const availableTags = tags.filter(t => !this.selectedTags.some(x => x.id === t.id))
         let filtered = availableTags.filter(t => t.name.toLowerCase().includes(query)).slice(0, 4)
         if (filtered.length === 0) {
            filtered = availableTags.slice(0, 4)
         }
         this.tagSuggestionsInclude = filtered
      },

      addSelectedTag(tag) {
         if (!this.selectedTags.find(t => t.id === tag.id)) {
            this.selectedTags.push(tag)
         }
         this.tagQueryInclude = ""
         this.tagSuggestionsInclude = []
         this.searchTags()
      },

      removeSelectedTag(tag) {
         this.selectedTags = this.selectedTags.filter(t => t.id !== tag.id)
      },

      searchExtensions() {
         const q = this.extensionQuery.trim()
         const available = this.allExtensions.filter(e => !this.selectedExtensions.includes(e))
         let suggestions = [...available]

         if (q) {
            const normalized = q.startsWith('.') ? q : `.${q}`
            const stripped = normalized.slice(1)
            if (!this.selectedExtensions.includes(stripped) && !available.includes(stripped)) {
               suggestions = [normalized, ...suggestions]
            }
         }

         const lowerQuery = q.toLowerCase()
         suggestions = suggestions.filter(s => s.toLowerCase().includes(lowerQuery))
         this.extensionSuggestions = suggestions.slice(0, 4)
      },

      addExtension(ext) {
         this.selectedExtensions.push(ext)
         this.extensionQuery = ""
         this.extensionSuggestions = []
         this.searchExtensions()
      },

      removeExtension(ext) {
         this.selectedExtensions = this.selectedExtensions.filter(e => e !== ext)
         this.searchExtensions()
      },

      onPropertyChange() {
         this.range = { from: null, to: null, value: null, mode: "between" }
      },

      submit: onceAtATime(function() {
         this.saveCurrentStateToStore()
         this.currentPrompt.confirm()
         this.closeHover()
      })
   }
}
</script>

<style scoped>
.card {
   display: flex;
   flex-direction: column;
   max-height: 80vh;
}
.card-content {
   flex: 1;
   overflow-y: auto;
   min-height: 0;
}
.range-mode {
   margin-top: 0.5em;
   width: 100%;
}
.range-inputs {
   display: flex;
   gap: 8px;
}
.range-inputs input {
   max-width: 10.85em;
}
.range-group {
   display: flex;
   flex-direction: column;
   gap: 6px;
}
.tags-container {
   display: flex;
   flex-wrap: wrap;
   gap: 8px;
   margin-bottom: 12px;
}
.tags-container:not(:empty) {
   margin-top: 10px;
}
.tag {
   display: inline-flex;
   align-items: center;
   gap: 6px;
   padding: 4px 10px;
   border-radius: 16px;
   background-color: var(--background);
   border: 1px solid rgba(255, 255, 255, 0.08);
   font-size: 13px;
   line-height: 1;
}
.tag-icon {
   font-size: 16px;
   color: var(--icon-yellow);
   display: flex;
   align-items: center;
}
.remove-tag-button {
   display: flex;
   align-items: center;
   justify-content: center;
   width: 18px;
   height: 18px;
   margin-left: 4px;
   padding: 0;
   border: none;
   background: transparent;
   cursor: pointer;
}
.close-icon {
   font-size: 14px;
   color: var(--textSecondary);
   transition: color 0.15s ease;
}
.remove-tag-button:hover .close-icon {
   color: var(--icon-red);
}
.suggestions {
   margin-top: 4px;
   margin-bottom: 10px;
   border-radius: 6px;
   overflow: hidden;
   background: var(--surfaceSecondary);
   border: 1px solid rgba(255, 255, 255, 0.08);
}
.suggestion {
   padding: 8px 10px;
   cursor: pointer;
   font-size: 13px;
}
.suggestion:hover {
   background: rgba(255, 255, 255, 0.06);
}
.checkbox-group {
   padding-bottom: 0.5em;
}
.fade-enter-active {
   transition: opacity 0.25s ease, transform 0.25s ease;
}
.fade-leave-active {
   transition: opacity 0.15s ease, transform 0.15s ease;
}
.fade-enter-from {
   opacity: 0;
   transform: translateY(-8px);
}
.fade-leave-to {
   opacity: 0;
   transform: translateY(-4px);
}
</style>