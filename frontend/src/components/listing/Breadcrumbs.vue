<template>
   <div class="breadcrumbs">
      <component
         :is="element"
         :aria-label="$t('files.home')"
         :class="breadcrumbClass(user?.root)"
         :title="$t('files.home')"
         :to="base || ''"
         draggable="false"
         @dragenter="dragEnter(user?.root)"
         @dragleave="dragLeave"
         @drop="drop(user?.root)"
         @dragover.prevent
      >
         <i class="material-icons">home</i>
      </component>

      <span v-for="folder in breadcrumbs" :key="folder.id">
         <span class="chevron">
            <i class="material-icons">keyboard_arrow_right</i>
         </span>
         <component
            :is="element"
            :ref="folder.id"
            :class="breadcrumbClass(folder.id)"
            :to="base + `/` + folder.id + lockFrom(folder)"
            draggable="false"
            @dragenter="dragEnter(folder.id)"
            @dragleave="dragLeave"
            @drop="drop(folder.id)"
            @dragover.prevent
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
import { move } from "@/api/item.js"

export default {
   name: "breadcrumbs",

   props: ["base", "folderList"],

   data() {
      return {
         draggedOverFolderId: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["selected", "user"]),

      element() {
         return "router-link"
      },
      //todo
      maxBreadcrumbs() {
         return isMobile() ? 3 : 5
      },

      breadcrumbs() {
         let folders = [...this.folderList]
         if (folders.length >= this.maxBreadcrumbs) {
            while (folders.length !== this.maxBreadcrumbs) {
               folders.shift()
            }
            folders[0].name = "..."
         }
         return folders
      },

      selectedCount() {
         return this.selected.length || 0
      }
   },

   methods: {
      lockFrom(folder) {
         if (this.base === "/files") {
            if (folder.lockFrom) return "/" + folder.lockFrom
         }
         return ""
      },

      dragEnter(folderId) {
         if (this.canDrop(folderId)) {
            this.draggedOverFolderId = folderId
         }
      },

      dragLeave() {
         this.draggedOverFolderId = null
      },

      canDrop(folder_id) {
         return this.selected[0]?.parent_id !== folder_id && this.$route.name === "Files"
      },

      async drop(folder_id) {
         if (!this.canDrop(folder_id) || this.selectedCount === 0) return

         let listOfIds = this.selected.map((obj) => obj.id)
         let res = await move({ ids: listOfIds, new_parent_id: folder_id })

         let message = this.$t("toasts.movingItems")
         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })
         this.dragLeave()
      },

      breadcrumbClass(folderId) {
         return {
            "breadcrumb-hovered": this.draggedOverFolderId === folderId,
            "breadcrumb-faded": this.draggedOverFolderId && this.draggedOverFolderId !== folderId
         }
      }
   }
}
</script>
<style scoped>
.breadcrumb-hovered {
 font-weight: bold;
 opacity: 1;
 transition: all 0.2s ease-in-out;
}

.breadcrumb-hovered i.material-icons {
 font-size: 32px;
 text-shadow: 0 0 2px black;
}

.breadcrumb-faded {
 opacity: 0.5;
 transition: opacity 0.2s ease-in-out;
}
</style>
