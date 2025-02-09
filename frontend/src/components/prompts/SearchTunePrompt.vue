<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.searchTune") }}</h2>
    </div>

    <div class="card-content">

      <div>
        <label>{{ $t("prompts.fileType") }}</label>
        <select class="input input--block styled-select" v-model="fileType">
          <option value="all">{{ $t("prompts.all") }}</option>
          <option v-for="type in fileTypes" :key="type" :value="type">{{ type }}</option>
        </select>
      </div>

      <div>
        <label>{{ $t("prompts.extension") }}</label>
        <input
          class="input input--block styled-input"
          type="text"
          v-focus
          v-model.trim="extension"
          :placeholder="$t('prompts.enterExtension')"
        />
      </div>

      <div class="checkbox-group">
        <label>
          <input type="checkbox" v-model="includeFiles" />
          {{ $t("prompts.includeFiles") }}
        </label>
      </div>

      <div class="checkbox-group">
        <label>
          <input type="checkbox" v-model="includeFolders" />
          {{ $t("prompts.includeFolders") }}
        </label>
      </div>

      <div>
        <label>{{ $t("prompts.resultLimit") }}</label>
        <input
          class="input input--block styled-input"
          type="number"
          v-model.number="resultLimit"
          :placeholder="$t('prompts.enterResultLimit')"
        />
      </div>
      <!-- Order By Field -->
      <div>
        <label>{{ $t("prompts.orderBy") }}</label>
        <select class="input input--block styled-select" v-model="orderBy">
          <option value="created_at">{{ $t("prompts.orderByCreatedAt") }}</option>
          <option value="duration">{{ $t("prompts.orderByDuration") }}</option>
          <option value="size">{{ $t("prompts.orderBySize") }}</option>
          <option value="name">{{ $t("prompts.orderByName") }}</option>
        </select>
      </div>
      <div class="checkbox-group">
        <label>
          <input type="checkbox" v-model="ascending" />
          {{ $t("prompts.ascending") }}
        </label>
      </div>
      <div>
        <label>{{ $t("prompts.tags") }}</label>
        <input
          class="input input--block styled-input"
          type="text"
          v-model.trim="tags"
          :placeholder="$t('prompts.enterTags')"
        />
      </div>
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="closeHover()"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        @click="submit()"
        class="button button--flat"
        type="submit"
        :aria-label="$t('buttons.submit')"
        :title="$t('buttons.submit')"
      >
        {{ $t("buttons.ok") }}
      </button>
    </div>
  </div>
</template>

<script>

import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"

export default {
   name: "filterFiles",
   data() {
      return {
         fileType: null,
         extension: null,
         includeFiles: null,
         includeFolders: null,
         resultLimit: null,
         fileTypes: ["application", "audio", "document", "image", "video", "text"],
         tags: null,
         orderBy: null,
         ascending: null
      }
   },
   computed: {
      ...mapState(useMainStore, ["searchFilters", "currentPrompt"])
   },
   created() {
      this.fileType = this.searchFilters.type || "all"
      this.extension = this.searchFilters.extension || null
      this.includeFiles = this.searchFilters.files
      this.includeFolders = this.searchFilters.folders
      this.resultLimit = this.searchFilters.resultLimit || 100
      this.tags = this.searchFilters.tags || ""
      this.orderBy = this.searchFilters.orderBy || "size"
      this.ascending = this.searchFilters.ascending || false
   },
   methods: {
      ...mapActions(useMainStore, ["setSearchFilters", "setDisabledCreation", "resetSelected", "closeHover", "setSortingBy", "setSortByAsc", "setError"]),

      async submit() {


         this.setDisabledCreation(true)
         this.resetSelected()

         this.resultLimit = this.resultLimit || 1

         if (this.fileType === "all") this.fileType = null

         let searchFilterDict = {
            files: this.includeFiles,
            folders: this.includeFolders,
            resultLimit: this.resultLimit,
            tags: this.tags,
            orderBy: this.orderBy,
            ascending: this.ascending
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

      }
   }
}
</script>

<style scoped>
.checkbox-group {
 margin-bottom: 15px;
}
</style>
