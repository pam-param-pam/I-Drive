<template>
  <div class="item-wrapper">
    <div
      ref="wrapper"
      :aria-label="item.name"
      :aria-selected="isSelected"
      :data-dir="item.isDir"
      :data-id="item.id"
      :data-type="type"
      :draggable="isDraggable"
      class="item"
      role="button"
      tabindex="0"
      @click="click"
      @dblclick="open"
      @dragover="dragOver"
      @dragstart="dragStart"
      @drop="drop"
    >
      <div :style="divStyle">
        <img
          v-if="imageSrc"
          :draggable="false"
          @mouseenter="handleHoverStart"
          @mouseleave="handleHoverEnd"
          v-lazy="{ src: imageSrc }"
        />
        <i v-else :style="iconStyle" class="material-icons"></i>
      </div>
      <div class="name">
        <p>{{ item.name }}</p>
      </div>
      <div class="size">
        <p :data-order="humanSize()" class="size">{{ humanSize() }}</p>
      </div>
      <div class="created">
        <p>{{ item.created }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import { filesize } from '@/utils'
import { move } from '@/api/item.js'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { isMobile } from '@/utils/common.js'
import dayjs from "@/utils/dayjsSetup.js"

export default {
   name: 'item',

   emits: ['onOpen', 'onLongPress'],

   props: ['readOnly', 'item', 'imageWidth', 'imageHeight'],

   data() {
      return {
         clickTimer: null,
         clickDelay: 210
      }
   },

   computed: {
      ...mapState(useMainStore, ["perms", "selected", "settings", "items", "selectedCount", "sortedItems"]),
      imageSrc() {
         let size = this.settings.viewMode === 'height grid' ? "512" : "128"
         if (this.type === 'Raw image') {
            if (this.item.preview_url) return this.item.preview_url
            if (this.item.download_url) return this.item.download_url
         }
         if (['Video', 'Audio', 'Image'].includes(this.type) && this.item.thumbnail_url) {
            return this.item.thumbnail_url + "?size=" + size
         }
         if (this.type === "Image") {
            return this.item.download_url
         }
         return null
      },
      type() {
         if (this.item.isDir) return 'folder'
         return this.item.type
      },
      isSelected() {
         return this.selected.some((obj) => obj.id === this.item.id)
      },
      isDraggable() {
         return this.readOnly === false && this.perms?.modify
      },
      canDrag() {
         return !this.readOnly
      },
      canDrop() {
         if (!this.item.isDir || this.readOnly !== false) return false

         for (let item of this.selected) {
            if (item === this.item) {
               return false
            }
            if (item.id === this.item.id) {
               return false
            }
         }
         return true
      },

      iconStyle() {
         if (this.settings.viewMode === 'height grid') {
            return `font-size: ${this.imageHeight / 25}em; padding-top: 15px;`
         }
         if (this.settings.viewMode === 'width grid') {
            return `font-size: ${this.imageHeight / 17}em; padding-top: 15px;`
         }
         return null
      },
      divStyle() {
         if (this.settings.viewMode.includes('grid')) {
            return `min-width: ${this.imageWidth}px; height: ${this.imageHeight}px;  vertical-align: text-bottom; display: flex; justify-content: center; align-items: center;`
         }
         return null
      }
   },

   methods: {
      ...mapActions(useMainStore, ['setLastItem', 'addSelected', 'removeSelected', 'resetSelected', 'setPopupPreviewURL', 'clearPopupPreviewURL']),

      humanSize() {
         if (this.item.isDir) return '-'
         return filesize(this.item.size)
      },

      handleHoverStart() {
         this.hoverTimer = setTimeout(() => {

            this.setPopupPreviewURL(this.imageSrc)
         }, 500)
      },
      handleHoverEnd() {
         clearTimeout(this.hoverTimer)
         this.clearPopupPreviewURL()
      },


      humanTime() {
         const date = this.item.created

         if (this.settings.dateFormat) {
            return dayjs(date, 'YYYY-MM-DD HH:mm').format('DD/MM/YYYY, hh:mm')
         }
         return dayjs(date, 'YYYY-MM-DD HH:mm').fromNow()
      },

      dragStart(event) {
         if (!this.canDrag) {
            event.preventDefault()
            return
         }
         if (this.selectedCount === 0) {
            this.addSelected(this.item)
            return
         }

         if (!this.isSelected) {
            this.resetSelected()
            this.addSelected(this.item)
         }
      },

      dragOver(event) {
         event.preventDefault()

         if (!this.canDrop) {
            return
         }

         let el = event.target
         for (let i = 0; i < 5; i++) {
            if (!el.classList.contains('item')) {
               el = el.parentElement
            }
         }
         el.style.opacity = 1
      },

      async drop(event) {
         if (event.dataTransfer.files.length > 0) return
         if (!this.canDrop) return
         if (this.selectedCount === 0) return

         let listOfIds = this.selected.map((obj) => obj.id)
         let res = await move({ ids: listOfIds, new_parent_id: this.item.id })

         let message = this.$t('toasts.movingItems')
         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })

         this.resetSelected()
      },

      open() {
         if (this.item.isDir) this.setLastItem(null)

         this.$emit('onOpen', this.item)
      },

      openContextMenu(event) {
         this.$emit('onLongPress', event, this.item)
      },

      click(event) {
         if (isMobile()) {
            if (this.clickTimer) {
               clearTimeout(this.clickTimer)
               this.clickTimer = null
               return
            }

            this.clickTimer = setTimeout(() => {
               this.clickTimer = null

               if (isMobile()) {
                  this.openContextMenu(event)
               }
            }, this.clickDelay)
         }

         // Deselect items if no shift or ctrl key is pressed and there are selected items
         // then add current item to selected if it wasn't previously selected
         if (!event.ctrlKey && !event.shiftKey && this.selected.length > 0) {
            let shouldAdd =
               (!this.isSelected || this.selected.length >= this.items.length) &&
               this.items.length > 1
            this.resetSelected()
            if (shouldAdd) {
               this.addSelected(this.item)
            }
            return
         }

         // Shift+Click functionality for range selection
         if (event.shiftKey && this.selectedCount > 0) {
            let fromItem = this.item
            let toItem = this.selected[this.selected.length - 1]

            let fromIndex = fromItem.index
            let toIndex = toItem.index

            let start = Math.min(fromIndex, toIndex)
            let end = Math.max(fromIndex, toIndex)
            this.resetSelected()

            this.sortedItems.forEach((item) => {
               if (item.index >= start && item.index <= end) {
                  this.addSelected(item)
               }
            })
            return
         }
         // Remove the selected item if it is already selected and there are selected items
         if (this.isSelected) {
            this.removeSelected(this.item)
         } else {
            this.addSelected(this.item)
         }
      }
   }
}
</script>
<style scoped>
/* ========================= */
/* 📝 GRID VIEW STYLES       */
/* ========================= */
.grid .item-wrapper:hover {
 box-shadow:
   0 1px 3px rgba(0, 0, 0, 0.12),
   0 1px 2px rgba(0, 0, 0, 0.24) !important;
 background: var(--light-blue);
 transform: scale(1.03);
}

.grid .item-wrapper {
 border-radius: 10px;
 margin: 0.5em;
 background-color: var(--surfacePrimary);
 overflow: hidden;
 box-shadow:
   rgba(0, 0, 0, 0.06) 0 1px 3px,
   rgba(0, 0, 0, 0.12) 0 1px 2px;
}

.grid .item-wrapper .item {
 display: flex;
 flex-direction: column;
 text-align: center;
 transition:
   0.1s ease background,
   0.1s ease opacity;
 cursor: pointer;
 user-select: none;
}

.grid .item-wrapper .item img {
 margin-top: 0.5em;
 max-width: 100%;
 object-fit: cover;
 height: 100%;
}

.grid .item-wrapper .item .name p {
 text-overflow: ellipsis;
 overflow: hidden;
 font-size: 15px;
 margin: 1.25em 2em 0.75em;
 white-space: nowrap;
}

.grid .item-wrapper .item .created,
.grid .item-wrapper .item .size {
 display: none;
}

.grid .item-wrapper [aria-selected='true'] {
 background: #c4e6ff;
}

.grid .item-wrapper [data-dir='true'] p {
 font-size: 20px !important;
 font-weight: 300;
 margin-top: 0.5em !important;
}

/* ========================= */
/* 📝 LIST VIEW STYLES       */
/* ========================= */

.list .item-wrapper {
 width: 100%;
 display: flex;
 flex-direction: column;
}

.list .item-wrapper .item {
 display: flex;
 align-items: center;
 border-bottom: 1px solid var(--divider);
 padding: 8px 12px;
 cursor: pointer;
 transition: background-color 0.2s ease-in-out;
}

.list .item-wrapper .item:hover {
 background-color: var(--surfaceSecondary);
}

.list .item-wrapper .item > div {
 padding: 4px 8px;
 overflow: hidden;
 text-overflow: ellipsis;
 white-space: nowrap;
}

.list .item-wrapper .item > div:first-child {
 flex: 0 0 40px;
 text-align: center;
}

.list .item-wrapper .name {
 flex: 2;
 font-weight: 500;
}

.list .item-wrapper .size {
 flex: 1;
 text-align: right;
 color: #666;
 font-size: 0.9em;
}

.list .item-wrapper .created {
 flex: 1.5;
 text-align: right;
 color: #999;
 font-size: 0.9em;
}

.list .item-wrapper img {
 max-width: 32px;
 max-height: 32px;
 object-fit: cover;
 border-radius: 4px;
}

.list .item-wrapper .material-icons {
 font-size: 24px;
 color: #666;
}
</style>