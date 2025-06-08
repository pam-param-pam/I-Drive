<template>
   <div>
      <ul class="file-list">
         <li
            v-for="item in dirs"
            :key="item.id"
            :aria-label="item.name"
            :aria-selected="selectedFolder === item"
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
import { getDirs } from '@/api/folder.js'
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'

export default {
   name: 'folder-list',

   emits: ['update:current'],

   data() {
      return {
         selectedFolder: null,
         dirs: [],
         nav: null
      }
   },

   computed: {
      ...mapState(useMainStore, ['currentFolder', 'selected'])
   },

   mounted() {
      this.fetchData(this.currentFolder)
   },

   methods: {
      ...mapActions(useMainStore, ['showHover']),

      async fetchData(folder) {
         let res = await getDirs(folder.id)

         let dirs = res.children

         if (res.parent_id) {
            let folderBack = { name: '..', id: res.parent_id }
            dirs.unshift(folderBack)
         }

         this.dirs = dirs.filter((folder) => this.selected[0].id !== folder.id)
         this.nav = { name: res.name, id: res.id, folder_path: res.folder_path }
         this.$emit('update:current', this.nav)
      },

      async next(event) {
         let current = event.currentTarget.dataset.item
         current = JSON.parse(current)
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

.file-list span {
   overflow: hidden;
   text-overflow: ellipsis;
   white-space: nowrap;
   flex-grow: 1;
}
</style>
