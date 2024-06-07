<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.searchTune") }}</h2>
    </div>

    <div class="card-content">
      <p>{{ $t("prompts.filterMessage") }}:</p>

      <div>
        <label>{{ $t("prompts.fileType") }}</label>
        <select
          class="input input--block styled-select"
          v-model="fileType"
        >
          <option value="all">{{ $t("prompts.all") }}</option>
          <option v-for="type in fileTypes" :key="type" :value="type">{{ type }}</option>
        </select>
      </div>

      <div>
        <label>{{ $t("prompts.extension") }}</label>
        <input
          class="input input--block styled-input"
          type="text"
          v-model.trim="extension"
        />
      </div>

      <div class="checkbox-group">
        <label>
          <input
            type="checkbox"
            v-model="includeFiles"
          />
          {{ $t("prompts.includeFiles") }}
        </label>
      </div>

      <div class="checkbox-group">
        <label>
          <input
            type="checkbox"
            v-model="includeFolders"
          />
          {{ $t("prompts.includeFolders") }}
        </label>
      </div>

      <div>
        <label>{{ $t("prompts.showLimit") }}</label>
        <input
          class="input input--block styled-input"
          type="number"
          v-model.number="showLimit"
        />
      </div>
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="$store.commit('closeHover')"
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
import { mapGetters, mapMutations, mapState } from "vuex";

export default {
  name: "filterFiles",
  data() {
    return {
      fileType: null,
      extension: null,
      includeFiles: null,
      includeFolders: null,
      showLimit: null,
      fileTypes: ["application", "audio", "document", "image", "video", "text"],
    };
  },
  computed: {
    ...mapState(["searchFilters"]),
    ...mapGetters(["currentPrompt"]),
  },
  created() {
    console.log(this.searchFilters)
    this.fileType = this.searchFilters.type || "all"
    this.extension = this.searchFilters.extension || null
    this.includeFiles = this.searchFilters.files
    this.includeFolders = this.searchFilters.folders
    this.showLimit = this.searchFilters.showLimit || 20
  },
  methods: {
    ...mapMutations(["setSearchFilters"]),

    async submit() {
      this.$store.commit("setDisableCreation", true)
      this.$store.commit("resetSelected")
      if (this.fileType === "all") this.fileType = null

      let searchFilterDict = {
        files: this.includeFiles,
        folders: this.includeFolders,
        showLimit: this.showLimit,
      };
      if (this.fileType !== null) searchFilterDict.type = this.fileType
      if (this.extension !== null) searchFilterDict.extension = this.extension

      this.setSearchFilters(searchFilterDict)
      try {

        this.currentPrompt.confirm()
      } catch (error) {
        console.log(error)
      } finally {
        this.$store.commit("closeHover")
      }

    },
  },
};
</script>

<style scoped>
.checkbox-group {
 margin-bottom: 15px;
}
</style>
