<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.editTags") }}</h2>
    </div>

    <div class="card-content">
      <p>
        {{ $t("prompts.editTagsDescription") }}
      </p>

      <div class="tags-container">
        <span
          v-for="(tag, index) in selected[0].tags"
          :key="index"
          class="tag"
        >
          <i class="material-icons tag-icon">sell</i>

          {{ tag }}
          <button
            class="remove-tag-button"
            @click="removeTag(tag)"
            :aria-label="$t('buttons.removeTag', { tag })"
          >
            <i class="material-icons close-icon">close</i>

          </button>

        </span>
      </div>

      <div class="tag-input-container">
        <input
          class="input input--block"
          v-focus
          type="text"
          v-model.trim="tagName"
          :placeholder="$t('prompts.enterTagName')"
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
        v-if="tagName!==''"
        @click="submit()"
        class="button button--flat"
        type="submit"
        :aria-label="$t('buttons.addTag')"
        :title="$t('buttons.addTag')"
      >
        {{ $t("buttons.addTag") }}
      </button>
      <button
        v-else
        @click="submit()"
        class="button button--flat"
        type="submit"
        :aria-label="$t('buttons.ok')"
        :title="$t('buttons.ok')"
      >
        {{ $t("buttons.ok") }}
      </button>
    </div>
  </div>
</template>

<script>
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { addTag, removeTag } from "@/api/files.js"


export default {
   name: "EditTags",

   data() {
      return {
         tagName: ""
      }
   },

   computed: {
      ...mapState(useMainStore, ["selected"])

   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "resetSelected", "updateItem"]),

      async submit() {
         if (this.tagName === "") {
            this.closeHover()
         }

         await addTag({ "tag_name": this.tagName, "file_id": this.selected[0].id })
         let file = this.selected[0]
         file.tags = [...file.tags, this.tagName];

         this.tagName = ""

         this.updateItem(file)
      },
      async removeTag(tagName) {
         await removeTag({ "tag_name": tagName, "file_id": this.selected[0].id })

         let file = this.selected[0]
         file.tags = file.tags.filter(tag => tag !== tagName)
         this.updateItem(file)
      }

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
 padding-bottom: 0 !important;
 padding-top: 4px !important;
}
.tag-icon {
 font-size: 16px;
 margin-right: 6px;
}


</style>