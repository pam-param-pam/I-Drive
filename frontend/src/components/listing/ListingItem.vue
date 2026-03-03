<template>
   <div class="item-wrapper">
      <span
         v-if="multiSelection"
         class="multi-select-hitbox"
         v-touch:tap.stop="onMultiSelectTap"
      >
        <button
           class="multi-select-toggle"
           :aria-pressed="isSelected"
           tabindex="-1"
        />
      </span>

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
         @click.left="onLeftClick"
         @click.right.prevent="onRightClick"
         @dblclick="onDoubleClick"
         v-touch:hold.prevent="onLongPress"
         v-touch:tap.prevent="onMobileTap"
         @dragover="dragOver"
         @dragstart="dragStart"
         @drop="drop"
      >
         <div :style="divStyle">
            <img
               v-if="imageSrcSmall"
               :draggable="false"
               @mouseenter="handleHoverStart"
               @mouseleave="handleHoverEnd"
               @error="handleImageError"
               v-lazy="{ src: imageSrcSmall }"
            />
            <i v-else :style="iconStyle" class="material-icons"></i>
         </div>

         <div class="name" :title="item.name">
            <p>{{ item.name }}</p>
         </div>

         <div class="size">
            <p :data-order="humanSize(item.size)">
               {{ humanSize(item.size) }}
            </p>
         </div>

         <div class="created">
            <p>{{ humanTime(item.created) }}</p>
         </div>
      </div>
   </div>
</template>


<script>
import { filesize } from "@/utils"
import { move } from "@/api/item.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { humanTime, isMobile } from "@/utils/common.js"
import { toRaw } from "vue"
import { getFileRawData } from "@/api/files.js"

export default {
   name: "item",

   emits: ["onOpen", "onContextMenuOpen", "onHideContextMenu"],

   props: ["readOnly", "item", "imageWidth", "imageHeight"],

   data() {
      return {
         clickTimer: null,
         clickDelay: 210,
         fallback: false
      }
   },

   computed: {
      ...mapState(useMainStore, ["perms", "selected", "settings", "items", "selectedCount", "sortedItems", "multiSelection", "contextMenuState", "areImagesBlocked"]),
      imageSrc() {
         if (this.item.size === 0) return null
         if (this.item.thumbnail_url) {
            return this.item.thumbnail_url
         }
         if (this.type === "Image") {
            return this.item.download_url
         }
         return null
      },
      imageSrcSmall() {
         let size = this.settings.viewMode === "height grid" ? "512" : "256"
         if (!this.imageSrc) return
         if (this.fallback || this.areImagesBlocked) return "/img/failed.svg"
         return this.imageSrc + "?size=" + size
      },
      type() {
         if (this.item.isDir) return "folder"
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
         if (this.settings.viewMode === "height grid") {
            return `font-size: ${this.imageHeight / 25}em; padding-top: 15px;`
         }
         if (this.settings.viewMode === "width grid") {
            return `font-size: ${this.imageHeight / 17}em; padding-top: 15px;`
         }
         return null
      },
      divStyle() {
         if (this.settings.viewMode.includes("grid")) {
            return `min-width: ${this.imageWidth}px; height: ${this.imageHeight}px;  vertical-align: text-bottom; display: flex; justify-content: center; align-items: center;`
         }
         return null
      }
   },

   methods: {
      humanTime,
      ...mapActions(useMainStore, ["setLastItem", "addSelected", "removeSelected", "resetSelected", "setPopupPreview", "clearPopupPreview", "setMultiSelection", "blockImagesFor"]),

      humanSize(size) {
         if (!size) return "-"
         return filesize(this.item.size)
      },

      handleHoverStart() {
         if (this.item.isDir) return
         this.hoverTimer = setTimeout(() => {
            this.setPopupPreview({ "url": this.imageSrc, "file_id": this.item.id })
         }, 500)
      },
      handleHoverEnd() {
         clearTimeout(this.hoverTimer)
         this.clearPopupPreview()
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
            if (!el.classList.contains("item")) {
               el = el.parentElement
            }
         }
         el.style.opacity = 1
      },

      onLongPress() {
         if (!isMobile()) return

         this.setMultiSelection(true)
         this.hideContextMenu()
      },
      onDoubleClick(event) {
         this.$emit("onOpen", event)
      },
      onMultiSelectTap(event) {
         if (this.multiSelection) {
            if (this.isSelected) {
               this.removeSelected(this.item)
            } else {
               this.addSelected(this.item)
            }
         }
      },
      onMobileTap(event) {
         if (!isMobile()) return

         if (this.clickTimer) {
            // SECOND TAP → double tap
            clearTimeout(this.clickTimer)
            this.clickTimer = null
            this.$emit("onOpen", event)
            return
         }

         // FIRST TAP → wait
         this.clickTimer = setTimeout(() => {
            this.clickTimer = null
            //repackage event with x and y cords
            let touch =
               event.touches?.[0] ||
               event.changedTouches?.[0]

            if (!touch) return null

            let newEvent = {
               clientX: touch.clientX,
               clientY: touch.clientY
            }
            this.manageContextMenu(newEvent)
         }, this.clickDelay)
      },
      onRightClick(event) {
         //always display context menu (desktop only)
         this.manageContextMenu(event)
      },
      onLeftClick(event) {
         this.hideContextMenu()
         //always add to selected (desktop only)

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
      },
      async manageContextMenu(event) {
         if (this.contextMenuState.visible && isMobile()) {
            this.hideContextMenu()
            if (this.selectedCount === 1) {
               this.resetSelected()
            }
            return
         }

         if (this.selectedCount === 0) {
            this.addSelected(this.item)
         } else if (this.selectedCount === 1) {
            this.resetSelected()
            this.addSelected(this.item)
         }
         this.$emit("onContextMenuOpen", event)

      },
      hideContextMenu() {
         this.$emit("onHideContextMenu")
      },
      async drop(event) {
         if (event.dataTransfer.files.length > 0) return
         if (!this.canDrop) {
            this.$toast.error(this.$t("toasts.illegalMove"))
            return
         }
         if (this.selectedCount === 0) return

         let listOfIds = this.selected.map((obj) => obj.id)
         let res = await move({ ids: listOfIds, new_parent_id: this.item.id })

         let message = this.$t("toasts.movingItems")
         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })

         this.resetSelected()
      },

      open() {
         if (this.item.isDir) this.setLastItem(this.item)

         this.$emit("onOpen", this.item)
      },

      async handleImageError(event) {
         const img = event.target

         if (img.dataset.failed) return
         img.dataset.failed = "true"

         if (this.areImagesBlocked) {
            this.fallback = true
            return
         }

         try {
            const data = await getFileRawData(this.imageSrc)
            img.src = URL.createObjectURL(data)

         } catch (err) {
            const response = err?.response

            if (response?.status === 429) {
               const retryAfter = Number(response.headers?.["retry-after"]) || 30
               this.blockImagesFor(retryAfter)
            }

            this.fallback = true
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
 box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12),
 0 1px 2px rgba(0, 0, 0, 0.24) !important;
 background: var(--light-blue);
 transform: scale(1.03);
}

.grid .item-wrapper {
 position: relative; /* positioning context for button */
 border-radius: 10px;
 margin: 0.5em;
 background-color: var(--surfacePrimary);
 overflow: hidden;
 box-shadow: rgba(0, 0, 0, 0.06) 0 1px 3px,
 rgba(0, 0, 0, 0.12) 0 1px 2px;
}

.grid .item-wrapper .item {
 display: flex;
 flex-direction: column;
 text-align: center;
 transition: 0.1s ease background,
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
 cursor: pointer;
 transition: background-color 0.2s ease-in-out;
}

.list .item-wrapper .item:hover {
 background-color: var(--surfaceSecondary);
}

.list .item-wrapper .item > div {
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
 max-width: 48px;
 max-height: 48px;
 object-fit: cover;
 border-radius: 4px;
}

.list .item-wrapper .material-icons {
 font-size: 24px;
 color: #666;
}

.item-wrapper:hover .multi-select-toggle {
}

.multi-select-toggle {
 position: absolute;
 top: -8px;
 left: -8px;

 width: 14px;
 height: 14px;
 border-radius: 50%;

 background: #cfcfcf;
 border: 2px solid #fff;

 box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.15);

 cursor: pointer;
 padding: 0;

 touch-action: manipulation;
}

.multi-select-hitbox {
 position: absolute;
 top: 15px;
 left: 15px;

 width: 36px;
 height: 36px;

 display: flex;
 align-items: center;
 justify-content: center;

 z-index: 5;
}

.multi-select-toggle[aria-pressed="true"] {
 background: var(--dark-blue);
}

</style>