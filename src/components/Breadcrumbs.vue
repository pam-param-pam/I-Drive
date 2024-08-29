<template>
  <div class="breadcrumbs">
    <component
      :is="element"
      :to="base || ''"
      :aria-label="$t('files.home')"
      :title="$t('files.home')"
      draggable="false"
    >
      <i class="material-icons">home</i>
    </component>

    <span v-for="folder in breadcrumbs" :key="folder.id">
      <span class="chevron">
        <i class="material-icons">keyboard_arrow_right</i>
      </span>
      <component
        draggable="false"
        :is="element"
        :to="base + `/` + folder.id"
        @dragover="dragOver"
        @drop="drop"
      >
        {{ folder.name }}
      </component>
    </span>
  </div>
</template>


<script>
import {isMobile} from "@/utils/common.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapState} from "pinia"

export default {
   name: "breadcrumbs",
   props: ["base", "folderList"],

   computed: {
      ...mapState(useMainStore, ["currentFolder"]),
      element() {
         return "router-link"
      },

      maxBreadcrumbs() {
         //todo
         return 5
         if (isMobile()) {
            return 3
         } else return 5
      },

      breadcrumbs() {
         if (this.folderList.length >= this.maxBreadcrumbs) {
            while (this.folderList.length !== this.maxBreadcrumbs) {
               this.folderList.shift()
            }

            this.folderList[0].name = "..."
         }

         return this.folderList
      },

   },
   methods: {
      dragOver: function (event) {
         //todo

      },

      async drop(event) {
         //todo
      },

   },
}
</script>