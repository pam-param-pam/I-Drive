<template>
   <div ref="container" class="breadcrumbs">
      <!-- visible breadcrumbs -->
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
            :class="breadcrumbClass(folder.id)"
            :to="base + '/' + folder.id + lockFrom(folder)"
            draggable="false"
            @dragenter="dragEnter(folder.id)"
            @dragleave="dragLeave"
            @drop="drop(folder.id)"
            @dragover.prevent
         >
            {{ folder.name }}
         </component>
      </span>

      <!-- hidden measurement row -->
      <div ref="measureContainer" class="breadcrumbs-measure">

         <component
            :is="element"
            ref="homeMeasure"
            :to="base || ''"
         >
            <i class="material-icons">home</i>
         </component>

         <span v-for="folder in folderList" :key="'measure-' + folder.id">

            <span class="chevron">
               <i class="material-icons">keyboard_arrow_right</i>
            </span>

            <component
               :is="element"
               :ref="'measureCrumb' + folder.id"
               :to="base + '/' + folder.id + lockFrom(folder)"
            >
               {{ folder.name }}
            </component>

         </span>

      </div>

   </div>
</template>

<script>
import { useMainStore } from "@/stores/mainStore.js"
import { mapState } from "pinia"
import { move } from "@/api/item.js"
import throttle from "lodash.throttle"
import { isMobile } from "@/utils/common.js"

export default {

   name: "breadcrumbs",

   props: ["base", "folderList"],

   data() {
      return {
         draggedOverFolderId: null,
         visibleCount: 0,
         calculatingBreadcrumbs: false
      }
   },

   computed: {

      ...mapState(useMainStore, ["selected", "user"]),

      element() {
         return "router-link"
      },

      breadcrumbs() {

         const folders = [...this.folderList]

         if (folders.length <= this.visibleCount || this.visibleCount === 0) {
            return folders
         }

         const visible = folders.slice(-this.visibleCount)
         const lastHidden = folders[folders.length - this.visibleCount - 1]

         return [
            { ...lastHidden, name: "..." },
            ...visible
         ]
      },

      selectedCount() {
         return this.selected.length || 0
      }
   },

   watch: {
      folderList() {
         this.$nextTick(() => {
            this.calculateBreadcrumbs()
         })
      }
   },

   mounted() {

      this.resizeObserver = new ResizeObserver(() => {
         requestAnimationFrame(() => {
            this.calculateBreadcrumbs()
         })
      })

      this.resizeObserver.observe(this.$refs.container)

      this.$nextTick(() => {
         this.calculateBreadcrumbs()
      })
   },

   beforeUnmount() {
      this.resizeObserver?.disconnect()
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
         return this.selected[0]?.parent_id !== folder_id &&
            this.$route.name === "Files"
      },

      async drop(folder_id) {

         if (!this.canDrop(folder_id) || this.selectedCount === 0) return

         const ids = this.selected.map(obj => obj.id)

         const res = await move({
            ids,
            new_parent_id: folder_id
         })

         const message = this.$t("toasts.movingItems")

         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })

         this.dragLeave()
      },

      breadcrumbClass(folderId) {
         return {
            "breadcrumb-hovered":
               this.draggedOverFolderId === folderId,

            "breadcrumb-faded":
               this.draggedOverFolderId &&
               this.draggedOverFolderId !== folderId
         }
      },

      calculateBreadcrumbs: throttle(function() {
         if (this.calculatingBreadcrumbs) return
         this.calculatingBreadcrumbs = true

         try {

            const container = this.$refs.container
            if (!container) return

            const ellipsisSize = 60
            let containerWidth = container.clientWidth - ellipsisSize
            if (isMobile()) containerWidth = containerWidth * 2
            const homeWidth = this.$refs.homeMeasure?.$el?.offsetWidth || 0

            let usedWidth = homeWidth
            let visibleCount = 0

            const folders = [...this.folderList]

            for (let i = folders.length - 1; i >= 0; i--) {

               const folder = folders[i]

               const ref = this.$refs["measureCrumb" + folder.id]?.[0]
               const el = ref?.$el

               if (!el) continue

               const crumbWidth = el.offsetWidth

               if (usedWidth + crumbWidth > containerWidth) {
                  break
               }

               usedWidth += crumbWidth
               visibleCount++
            }
            if (visibleCount === 0) visibleCount = 1
            this.visibleCount = visibleCount

         } finally {
            this.calculatingBreadcrumbs = false
         }
      }, 200)

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

/* hidden measurement row */

.breadcrumbs-measure {
  position: absolute;
  visibility: hidden;
  pointer-events: none;
  white-space: nowrap;
  height: 0;
  overflow: hidden;
}

</style>