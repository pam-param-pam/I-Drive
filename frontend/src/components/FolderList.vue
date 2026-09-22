<template>
   <div>
      <ul class="file-list">
         <li
            v-for="item in dirs"
            :key="item.id"
            :aria-label="item.name"
            :aria-disabled="isDisabled(item)"
            :aria-selected="selectedFolder === item"
            :class="{ 'file-list__item--disabled': isDisabled(item) }"
            :data-item="JSON.stringify(item)"
            tabindex="0"
            @click="next"
         >
            <span>
               {{ item.name }}
            </span>
         </li>
      </ul>
   </div>
</template>

<script>
import { getItems } from "@/api/folder.js"
import { mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "folder-list",

   emits: ["update:current"],

   data() {
      return {
         selectedFolder: null,
         dirs: [],
         nav: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["currentFolder", "selected"])
   },

   mounted() {
      this.fetchData(this.currentFolder)
   },

   methods: {
      async fetchData(folder) {
         let res = await getItems(folder.id, folder.lockFrom)

         let dirs = res.folder.children
            .filter(item => item.isDir)
            .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }))

         if (res.folder.parent_id) {
            let folderBack = { name: "..", id: res.folder.parent_id }
            dirs.unshift(folderBack)
         }

         const folder_path = res.breadcrumbs.map(b => b.name).join("/")

         this.dirs = dirs
         this.nav = { name: res.folder.name, id: res.folder.id, folder_path: folder_path }
         this.$emit("update:current", this.nav)
      },

      isDisabled(folder) {
         return this.selected.some(item => item.id === folder.id || item.parent_id === folder.id)
      },

      async next(event) {
         let current = event.currentTarget.dataset.item
         current = JSON.parse(current)
         if (this.isDisabled(current)) return
         await this.fetchData(current)
      }
   }
}
</script>
<style scoped>
.file-list {
  padding-right: 1em;
}

.file-list li {
  display: flex;
  align-items: center;
  padding: 8px 12px;
   cursor: pointer;
}

.file-list__item--disabled {
   cursor: default;
   opacity: 0.5;
   pointer-events: none;
}

.file-list span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-grow: 1;
}
</style>
