<template>
  <div class="breadcrumbs">
    <component
      :is="element"
      :to="base || ''"
      :aria-label="$t('files.home')"
      :title="$t('files.home')"
      draggable="false"
      @drop="drop(user.root)"
      @dragenter="dragEnter(user.root)"
      @dragleave="dragLeave"
      :class="breadcrumbClass(user.root)"
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
        :ref="folder.id"
        :to="base + `/` + folder.id"
        @drop="drop(folder.id)"
        @dragenter="dragEnter(folder.id)"
        @dragleave="dragLeave"
        :class="breadcrumbClass(folder.id)"
      >
        {{ folder.name }}
      </component>
    </span>
  </div>
</template>




<script>
import { isMobile } from "@/utils/common.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapState } from "pinia"
import {move} from "@/api/item.js"

export default {
   name: "breadcrumbs",
   props: ["base", "folderList"],

   data() {
      return {
         draggedOverFolderId: null,
      }
   },

   computed: {
      ...mapState(useMainStore, ["selected", "user"]),

      element() {
         return "router-link"
      },

      maxBreadcrumbs() {
         return isMobile() ? 3 : 5
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
      dragEnter(folderId) {
         if (this.canDrop(folderId)) {
            this.draggedOverFolderId = folderId
            console.log(this.draggedOverFolderId)
         }
      },

      dragLeave() {
         this.draggedOverFolderId = null
      },

      canDrop(folder_id) {
         return (this.selected[0].parent_id !== folder_id) && this.$route.name === "Files"
      },
      async drop(folder_id) {


         if (!this.canDrop(folder_id)) return
         if (this.selectedCount === 0) return

         let listOfIds = this.selected.map(obj => obj.id)
         await move({ ids: listOfIds, "new_parent_id": folder_id })

         let message = this.$t('toasts.movedItems')
         this.$toast.success(message)
         this.dragLeave()
      },

      breadcrumbClass(folderId) {
         return {
            'breadcrumb-hovered': this.draggedOverFolderId === folderId,
            'breadcrumb-faded': this.draggedOverFolderId && this.draggedOverFolderId !== folderId,
         }
      }
   },
}
</script>
<style scoped>
.breadcrumb-hovered {
 font-weight: bold;
 opacity: 1;
}
.breadcrumb-hovered i.material-icons {
 font-size: 32px;
 text-shadow: 0 0 2px black;
}
.breadcrumb-faded {
 opacity: 0.5;
}
</style>