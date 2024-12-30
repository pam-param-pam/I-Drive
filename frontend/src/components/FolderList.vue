<template>
  <div>
    <p>
      {{ $t("prompts.moveTo") }} <code>{{ nav?.folder_path }}</code>
    </p>
    <ul class="file-list">
      <li
        v-for="item in dirs"
        @click="next"
        tabindex="0"
        :aria-label="item.name"
        :aria-selected="selectedFolder === item"
        :key="item.id"
        :data-item="JSON.stringify(item)"
      >
        <span>
          {{ item.name }}
        </span>
      </li>
    </ul>
  </div>
</template>

<script>
import {getDirs} from "@/api/folder.js"
import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"

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
      ...mapState(useMainStore, ["currentFolder", "selected"]),
   },

   mounted() {
      this.fetchData(this.currentFolder)
   },

   methods: {
      ...mapActions(useMainStore, ["showHover"]),
      async fetchData(folder) {
         //todo known bug that causes lack of state in move/file list:
         //when new prompt is displayed like folder password or new dir
         //the previous one is destroyed causing it to go back to initial state

         let res = await getDirs(folder.id)

         let dirs = res.children

         if (res.parent_id) {
            let folderBack = {name: "..", id: res.parent_id}
            dirs.unshift(folderBack)
         }

         console.log(this.selected)
         this.dirs = dirs.filter(folder => this.selected[0].id !== folder.id)
         this.nav = {name: res.name, id: res.id, folder_path: res.folder_path}
         this.$emit("update:current", this.nav)
      },

      async next(event) {
         let current = event.currentTarget.dataset.item
         current = JSON.parse(current)
         await this.fetchData(current)

      },
   },
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

.file-list span {
 overflow: hidden;
 text-overflow: ellipsis;
 white-space: nowrap;
 flex-grow: 1;
}
</style>