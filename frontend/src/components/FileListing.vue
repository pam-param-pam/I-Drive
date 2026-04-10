<template>
   <div class="wrapper">
      <PopupPreview v-if="!isMobile() && settings.popupPreview" />
      <header-bar>
         <Search
            v-if="headerButtons.search"
            :advanced="headerButtons.advancedSearch"
            ref="search"
            @exit="$emit('onSearchClosed')"
            @onSearchQuery="(query) => $emit('onSearchQuery', query)"
         />
         <title></title>
         <template #actions>
            <template v-if="!isMobile()">
               <action
                  v-if="headerButtons.locate"
                  :label="$t('buttons.locate')"
                  icon="location_on"
                  @action="locateItem"
               />
               <action
                  v-if="headerButtons.share"
                  :label="$t('buttons.share')"
                  icon="share"
                  show="share"
               />
               <action
                  v-if="headerButtons.modify"
                  :label="$t('buttons.rename')"
                  icon="mode_edit"
                  show="rename"
               />
               <action
                  v-if="headerButtons.move"
                  id="move-button"
                  :label="$t('buttons.moveFile')"
                  icon="forward"
                  show="move"
               />
               <action
                  v-if="headerButtons.moveToTrash"
                  id="moveToTrash-button"
                  :label="$t('buttons.moveToTrash')"
                  icon="delete"
                  show="moveToTrash"
               />
               <action
                  v-if="headerButtons.restore"
                  :label="$t('buttons.restoreFromTrash')"
                  icon="restore"
                  show="restoreFromTrash"
               />
               <action
                  v-if="headerButtons.delete"
                  id="delete-button"
                  :label="$t('buttons.delete')"
                  icon="delete_forever"
                  show="delete"
               />
            </template>
            <action
               v-if="headerButtons.lock"
               :label="$t('buttons.lockFolder')"
               icon="lock"
               show="editFolderPassword"
            />
            <action
               v-if="headerButtons.download"
               :counter="selectedCount"
               :label="$t('buttons.download')"
               icon="file_download"
               @action="$emit('download')"
            />
            <action
               v-if="headerButtons.upload"
               id="upload-button"
               :disabled="searchActive"
               :label="$t('buttons.upload')"
               icon="file_upload"
               @action="$emit('upload')"
            />
            <action :icon="viewIcon" :label="$t('buttons.switchView')" @action="switchView" />
            <action
               v-if="headerButtons.info"
               :disabled="selectedCount <= 0 && (searchActive || !this.currentFolder)"
               :label="$t('buttons.info')"
               icon="info"
               show="info"
            />

         </template>
      </header-bar>
      <loading-spinner />

      <template v-if="!error && !loading">
         <div v-if="sortedItems?.length === 0">
            <h2 class="message">
               <a href="https://www.youtube.com/watch?app=desktop&v=nGBYEUNKPmo">
                  <img :alt="$t('files.noFiles')" src="/img/youLookLonelyICanFixThat.jpg" />
               </a>
            </h2>
            <input
               id="upload-input"
               multiple
               style="display: none"
               type="file"
               @change="uploadInput($event)"
            />
            <input
               id="upload-folder-input"
               multiple
               style="display: none"
               type="file"
               webkitdirectory
               @change="uploadInput($event)"
            />
         </div>
         <div v-else class="wrapper">
            <div
               :class="viewMode + ' file-icons'"
               @dragenter.prevent
               @dragover.prevent
            >
               <div class="item header" draggable="false">
                  <div>
                     <p
                        :aria-label="$t('files.sortByName')"
                        :class="{ active: nameSorted }"
                        :title="$t('files.sortByName')"
                        class="nameSort"
                        role="button"
                        tabindex="0"
                        @click="sort('name')"
                     >
                        <span>{{ $t("files.name") }}</span>
                        <i class="material-icons">{{ nameIcon }}</i>
                     </p>

                     <p
                        :aria-label="$t('files.sortBySize')"
                        :class="{ active: sizeSorted }"
                        :title="$t('files.sortBySize')"
                        class="sizeSort"
                        role="button"
                        tabindex="0"
                        @click="sort('size')"
                     >
                        <span>{{ $t("files.size") }}</span>
                        <i class="material-icons">{{ sizeIcon }}</i>
                     </p>

                     <p
                        :aria-label="$t('files.sortByCreated')"
                        :class="{ active: createdSorted }"
                        :title="$t('files.sortByCreated')"
                        class="createdSort"
                        role="button"
                        tabindex="0"
                        @click="sort('created')"
                     >
                        <span>{{ $t("files.created") }}</span>
                        <i class="material-icons">{{ createdIcon }}</i>
                     </p>
                  </div>
               </div>

               <RecycleScroller
                  id="filesScroller"
                  ref="filesScroller"
                  v-slot="{ item }"
                  :grid-items="gridItems"
                  :item-secondary-size="tileWidth"
                  :item-size="tileHeight"
                  :items="sortedItems"
                  :prerender="500"
                  :style="scrollerClass"
                  class="scroller"
               >
                  <item
                     :key="item.id"
                     :ref="item.id"
                     :imageHeight="imageHeight"
                     :imageWidth="imageWidth"
                     :item="item"
                     :readOnly="readonly"
                     :tileHeight="tileHeight"
                     :tileWidth="tileWidth"
                     @onContextMenuOpen="showContextMenu($event, item)"
                     @onHideContextMenu="closeContextMenu"
                     @onOpen="$emit('onOpen', item)"
                  >
                  </item>
               </RecycleScroller>

               <input
                  id="upload-input"
                  multiple
                  style="display: none"
                  type="file"
                  @change="uploadInput($event)"
               />
               <input
                  id="upload-folder-input"
                  multiple
                  style="display: none"
                  type="file"
                  webkitdirectory
                  @change="uploadInput($event)"
               />
            </div>
         </div>

         <context-menu
            v-if="this.selectedCount > 0"
            :pos="contextMenuState.pos"
            :show="contextMenuState.visible"
            @hide="closeContextMenu"
         >
            <action
               v-if="headerButtons.locate"
               :label="$t('buttons.locate')"
               icon="location_on"
               @action="locateItem"
            />
            <action
               v-if="headerButtons.openInNewWindow && selected[0]?.isDir"
               :label="$t('buttons.openFolder')"
               icon="open_in_new"
               @action="$emit('openInNewWindow', selected[0])"
            />
            <action
               v-if="headerButtons.openInNewWindow && !selected[0]?.isDir"
               :label="$t('buttons.openFile')"
               icon="open_in_new"
               @action="$emit('openInNewWindow', selected[0])"
            />
            <action :label="$t('buttons.info')" icon="info" show="info" />

            <action
               v-if="headerButtons.modify"
               :label="$t('buttons.rename')"
               icon="mode_edit"
               show="rename"
            />
            <action
               v-if="headerButtons.moveToTrash"
               id="moveToTrash-button"
               :label="$t('buttons.moveToTrash')"
               icon="delete"
               show="moveToTrash"
            />
            <action
               v-if="headerButtons.restore"
               :label="$t('buttons.restoreFromTrash')"
               icon="restore"
               show="restoreFromTrash"
            />
            <action
               v-if="headerButtons.delete"
               id="delete-button"
               :label="$t('buttons.delete')"
               icon="delete_forever"
               show="delete"
            />
            <action
               v-if="headerButtons.move"
               id="move-button"
               :label="$t('buttons.moveFile')"
               icon="forward"
               show="move"
            />
            <action
               v-if="headerButtons.download"
               :label="$t('buttons.download')"
               icon="file_download"
               @action="$emit('download')"
            />
            <action
               v-if="headerButtons.share"
               :label="$t('buttons.share')"
               icon="share"
               show="share"
            />
            <action
               v-if="headerButtons.lock"
               :label="selected[0].isLocked ? $t('buttons.editLockFolder') : $t('buttons.lockFolder')"
               icon="lock"
               show="editFolderPassword"
            />
            <action
               v-if="headerButtons.copyShare"
               :label="$t('buttons.copyFileShareUrl')"
               icon="content_copy"
               @action="$emit('copyFileShareUrl')"
            />
            <action
               v-show="headerButtons.modifyFile && contextMenuState.advanced"
               id="tag"
               :label="$t('buttons.editTags')"
               icon="sell"
               show="EditTags"
            />
            <action
               v-show="
                  headerButtons.modifyFile &&
                  contextMenuState.advanced &&
                  (this.selected[0]?.type === 'Video' || this.selected[0]?.type === 'Image')
               "
               id="thumbnail"
               :label="$t('buttons.editThumbnail')"
               icon="image"
               show="EditThumbnail"
            />
            <action
               v-show="
                  headerButtons.modifyFile &&
                  contextMenuState.advanced &&
                  this.selected[0].type === 'Video'
               "
               id="subtitles"
               :label="$t('buttons.editSubtitles')"
               icon="subtitles"
               show="EditSubtitles"
            />
         </context-menu>
      </template>
   </div>
</template>

<script>
import Item from "@/components/listing/ListingItem.vue"
import { updateSettings } from "@/api/user.js"
import { isMobile } from "@/utils/common.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import ContextMenu from "@/components/ContextMenu.vue"
import Action from "@/components/header/Action.vue"
import HeaderBar from "@/components/header/HeaderBar.vue"
import Search from "@/components/Search.vue"
import { RecycleScroller } from "vue-virtual-scroller"
import loadingSpinner from "@/components/loadingSpinner.vue"
import PopupPreview from "@/components/listing/PopupPreview.vue"

export default {
   name: "FileListing",

   components: {
      PopupPreview,
      Search,
      HeaderBar,
      Action,
      Item,
      ContextMenu,
      RecycleScroller,
      loadingSpinner
   },

   props: {
      readonly: Boolean,
      headerButtons: {}
   },

   emits: ["uploadInput", "dropUpload", "upload", "onOpen", "dragEnter", "dragLeave", "onSearchClosed", "onSearchQuery", "download", "openInNewWindow", "copyFileShareUrl"],

   data() {
      return {
         dragCounter: 0,
         itemWeight: 0,
         searchItemsFound: null,

         //experimental
         tileWidth: 200,
         tileHeight: 200,
         imageHeight: 100,
         imageWidth: 100,
         numberOfTiles: 5,

         scrollInterval: null

      }
   },

   watch: {
      sortedItems() {
         // Ensures that the listing is displayed
         this.$nextTick(() => {
            this.calculateGridLayoutWrapper()
            this.scrollToLastItem()
         })
      },
      "$route.name"(newName, oldName) {
         if (newName === "Files" || newName === "Share") {
            this.scrollToLastItem()
         }
      }
   },

   mounted() {
      this.$nextTick(() => {
         this.calculateGridLayoutWrapper()
      })

      window.addEventListener("resize", this.calculateGridLayoutWrapper)

      // Add the needed event listeners to the window and document.
      window.addEventListener("keydown", this.keyEvent)

      if (!this.perms?.create) return
      document.addEventListener("dragover", this.preventDefault)
      document.addEventListener("dragenter", this.dragEnter)
      document.addEventListener("dragleave", this.dragLeave)
      document.addEventListener("drop", this.drop)
      document.addEventListener("drag", this.autoScroll)
      document.addEventListener("dragend", this.stopAutoScroll)
   },
   beforeRouteLeave() {
      clearTimeout(this.scrollToAnimationTimeout)
   },
   beforeUnmount() {
      this.resetSelected()

      if (this.multiSelection) {
         this.setMultiSelection(false)
      }

      // Remove event listeners before destroying this page.
      window.removeEventListener("keydown", this.keyEvent)
      window.addEventListener("resize", this.calculateGridLayoutWrapper)

      if (!this.user || !this.perms?.create) return
      document.removeEventListener("dragover", this.preventDefault)
      document.removeEventListener("dragenter", this.dragEnter)
      document.removeEventListener("dragleave", this.dragLeave)
      document.removeEventListener("drop", this.drop)
      document.removeEventListener("drag", this.autoScroll)
      document.removeEventListener("dragend", this.stopAutoScroll)
   },

   computed: {
      ...mapState(useMainStore, ["multiSelection", "contextMenuState", "selectedCount", "searchActive", "sortedItems", "lastItem", "items", "settings", "perms", "user", "selected", "loading", "error", "currentFolder", "selectedCount", "isLogged", "currentPrompt", "searchActive"]),

      viewMode() {
         if (this.settings.viewMode === "list") return "list"
         return "grid"

      },
      gridItems() {
         if (this.viewMode === "grid") {
            return this.numberOfTiles
         }
         return null
      },
      viewIcon() {
         const icons = {
            list: "view_module",
            "width grid": "view_list",
            "height grid": "view_column"
         }
         return icons[this.settings.viewMode]
      },
      nameSorted() {
         return this.settings.sortingBy === "name"
      },
      sizeSorted() {
         return this.settings.sortingBy === "size"
      },
      createdSorted() {
         return this.settings.sortingBy === "created"
      },
      ascOrdered() {
         return this.settings.sortByAsc
      },

      nameIcon() {
         if (this.nameSorted && !this.ascOrdered) {
            return "arrow_upward"
         }

         return "arrow_downward"
      },
      sizeIcon() {
         if (this.sizeSorted && this.ascOrdered) {
            return "arrow_downward"
         }

         return "arrow_upward"
      },
      createdIcon() {
         if (this.createdSorted && this.ascOrdered) {
            return "arrow_downward"
         }

         return "arrow_upward"
      },
      minusSize() {
         let component = this.$route.name
         if (component === "Files") return 80
         if (component === "Trash") return 105
         if (component === "Share") return 150
         return 0
      },
      scrollerClass() {
         return `height: calc(100% - ${this.minusSize}px);`
      }
   },

   methods: {
      ...mapActions(useMainStore, ["setMultiSelection", "openContextMenu", "closeContextMenu", "setSelected", "setLastItem", "addSelected", "resetSelected", "showHover", "setSortByAsc", "setSortingBy", "updateSettings"]),
      isMobile,

      async uploadInput(event) {
         this.$emit("uploadInput", event)
      },

      showContextMenu(event) {
         let advanced = event.ctrlKey || event.shiftKey

         let menuWidth = 200
         let menuHeight = advanced ? 450 : 400

         let offsetX = 40
         let offsetY = -40

         let viewportWidth = window.innerWidth
         let viewportHeight = window.innerHeight

         let posX = event.clientX + offsetX

         if (posX + menuWidth > viewportWidth) {
            posX = event.clientX - menuWidth - offsetX
         }

         posX = Math.max(0, Math.min(posX, viewportWidth - menuWidth))

         let posY = event.clientY + offsetY

         if (posY + menuHeight > viewportHeight) {
            posY = viewportHeight - menuHeight
         }

         posY = Math.max(0, posY)

         this.openContextMenu({
               pos: {
                  x: posX,
                  y: posY
               }, advanced: advanced
            }
         )
      },

      keyEvent(event) {
         // If prompts are shown return
         if (this.currentPrompt !== null) {
            return
         }

         // Esc!
         if (event.keyCode === 27) {
            // Reset files selection.
            this.resetSelected()
            this.closeContextMenu()
         }

         // Del!
         if (event.keyCode === 46) {
            if (!this.perms.delete || this.selectedCount === 0) return
            if (this.$route.name === "Trash") {
               this.showHover("delete")
            } else {
               this.showHover("moveToTrash")
            }
         }

         // F1!
         if (event.keyCode === 112) {
            event.preventDefault()
            this.showHover("info")
         }

         // F2!
         if (event.keyCode === 113) {
            if (!this.perms.modify || this.selectedCount !== 1) return
            this.showHover("rename")
         }

         // Ctrl is pressed
         if ((event.ctrlKey || event.metaKey)) {
            let key = event.key.toLowerCase()
            if (key === "a") {
               event.preventDefault()
               this.setSelected(this.sortedItems)
            }
         }
      },

      dragEnter(event) {
         this.$emit("dragEnter", event)
      },

      dragLeave() {
         this.$emit("dragLeave")
      },

      preventDefault(event) {
         event.preventDefault()
      },

      async drop(event) {
         event.preventDefault()
         if ((!this.currentFolder || this.searchActive) && event.dataTransfer.files.length > 0) {
            this.$toast.error(this.$t("toasts.uploadNotAllowedHere"))
            this.$emit("dragLeave")
            return
         }

         this.$emit("dropUpload", event)
      },

      autoScroll(event) {
         event.preventDefault()

         let filesScroller = this.$refs.filesScroller
         if (!filesScroller) return

         if (filesScroller.$el) {
            filesScroller = filesScroller.$el
         }

         let bounding = filesScroller.getBoundingClientRect()
         let cursorY = event.clientY
         let scrollSpeed = 0

         let topDistance = cursorY - bounding.top
         let bottomDistance = bounding.bottom - cursorY

         let maxSpeed = 1000
         let triggerZone = 200

         if (topDistance < triggerZone) {
            scrollSpeed = -Math.max(maxSpeed * (1 - topDistance / triggerZone), 5)
         } else if (bottomDistance < triggerZone) {
            scrollSpeed = Math.max(maxSpeed * (1 - bottomDistance / triggerZone), 5)
         } else {
            this.stopAutoScroll()
            return
         }
         if (!this.scrollInterval) {
            this.scrollInterval = setInterval(() => {
               filesScroller.scrollBy({ top: scrollSpeed })
            }, 30)
         }
      },

      stopAutoScroll() {
         if (this.scrollInterval) {
            clearInterval(this.scrollInterval)
            this.scrollInterval = null
         }
      },

      async sort(by) {
         let asc = false

         if (by === "name") {
            if (this.nameIcon === "arrow_upward") {
               asc = true
            }
         } else if (by === "size") {
            if (this.sizeIcon === "arrow_upward") {
               asc = true
            }
         } else if (by === "created") {
            if (this.createdIcon === "arrow_upward") {
               asc = true
            }
         }
         this.setSortingBy(by)
         this.setSortByAsc(asc)

         if (!this.isLogged) return
         await updateSettings({ sortingBy: by, sortByAsc: asc })
      },

      async locateItem() {
         this.$emit("onSearchClosed")
         let message = this.$t("toasts.locating")
         this.$toast.info(message)

         let item = this.selected[0]
         let parent_id = item.parent_id

         await this.$refs.search.exit()

         this.setLastItem(item)
         await this.$router.push({ name: "Settings" })
         this.$router.push({ name: "Files", params: { folderId: parent_id } })

         this.closeContextMenu()
      },

      async switchView() {
         let modes = {
            list: "width grid",
            "width grid": "height grid",
            "height grid": "list"
         }
         let data = {
            viewMode: modes[this.settings.viewMode] || "list"
         }

         await this.updateSettings(data)
         this.calculateGridLayoutWrapper()

         if (this.isLogged) {
            await updateSettings(data)
         }
      },

      calculateGridLayoutWrapper() {
         let element = document.getElementById("filesScroller")
         if (!element) return
         let width = element.clientWidth
         if (!isMobile()) width -= 5
         this.calculateGridLayout(width)
      },

      calculateGridLayout(containerWidth) {
         let maxTileWidth = 225
         if (isMobile()) {
            maxTileWidth -= 50
         }
         // Calculate the maximum number of tiles that can fit using the minimum width
         let numberOfTiles = Math.ceil(containerWidth / maxTileWidth)
         // if (numberOfTiles === 1) numberOfTiles = 2

         // Calculate the actual width of each tile
         let tileWidth = containerWidth / numberOfTiles

         this.numberOfTiles = numberOfTiles
         if (this.settings.viewMode === "width grid") {
            this.tileWidth = tileWidth
            this.tileHeight = tileWidth * 0.75
         } else if (this.settings.viewMode === "height grid") {
            this.tileWidth = tileWidth
            this.tileHeight = tileWidth * 1.5
         } else if (this.settings.viewMode === "list") {
            this.tileHeight = 50

         }

         this.imageHeight = this.tileHeight - 65
         if (isMobile()) this.imageHeight += 20
      },

      async scrollToLastItem() {
         function nextFrame() {
            return new Promise(resolve => requestAnimationFrame(resolve))
         }


         if (!this.lastItem) return

         await this.$nextTick()
         await nextFrame()

         const filesScroller = this.$refs.filesScroller
         if (!filesScroller) return

         const index = this.sortedItems.findIndex(file => file.id === this.lastItem.id) - this.numberOfTiles
         const lastItemId = this.lastItem.id

         filesScroller.scrollToItem(index)
         await nextFrame()

         const itemElement = this.$refs[lastItemId]
         if (!itemElement?.$el) return

         itemElement.$el.classList.add("pulse-animation")

         this.setLastItem(null)
         this.scrollToAnimationTimeout = setTimeout(() => {
            if (itemElement?.$el) {
               itemElement.$el.classList.remove("pulse-animation")
            }
         }, 3500)
      }
   }
}
</script>
<style scoped>
.message img {
  width: 60%;
}

.wrapper {
  padding-bottom: 0.5em;
}

.wrapper,
.list,
.grid {
  height: 100%;
}

.scroller {
  background-color: var(--background);
  padding-bottom: 2em;
}

.pulse-animation {
  animation: pulse 3s ease-out;
}

@keyframes pulse {
  0% {
    background: #80c6ff;
  }
  100% {
    background: var(--surfacePrimary);
  }
}

/* ============================= */
/* 📝 GRID SORT HEADER  STYLES   */
/* ============================= */

.grid .item.header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  font-family: Arial, sans-serif;
}

.grid .item.header > div {
  display: flex;
  gap: 10px;
}

.grid .item.header p {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  font-size: 14px;
  margin: 0;
  padding: 10px 15px 10px;
  border-radius: 3px;
  transition: color 0.3s;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.grid .item.header p.active {
  font-weight: bold;
}

.grid.item.header i.material-icons {
  font-size: 14px;
  color: inherit;
}








/* ============================= */
/* 📝 LIST SORT HEADER STYLES    */
/* ============================= */

.list .item.header {
   display: flex;
   align-items: center;

   padding: 8px 12px;

   background: var(--background);
   border-bottom: 1px solid var(--divider);

   position: sticky;   /* optional but usually desired */
   top: 0;
   z-index: 10;
}

/* inner container must behave like row */
.list .item.header > div {
   display: flex;
   width: 100%;
   align-items: center;
}

/* simulate "icon column" spacing */
.list .item.header > div::before {
   content: "";
   flex: 0 0 48px;
}

/* header cells */
.list .item.header p {
   display: flex;
   align-items: center;
   gap: 6px;

   margin: 0;
   padding: 6px 0;

   cursor: pointer;
   font-size: 13px;

   color: #666;
   transition: color 0.2s;
}

/* COLUMN WIDTHS — must match row flex */

/* name */
.list .item.header .nameSort {
   flex: 3;
}

/* size */
.list .item.header .sizeSort {
   flex: 1;
   justify-content: flex-end;
}

/* created */
.list .item.header .createdSort {
   flex: 1.5;
   justify-content: flex-end;
}

/* active sorting */
.list .item.header p.active {
   font-weight: 600;
   color: var(--textPrimary);
}

/* sort icon */
.list .item.header i.material-icons {
   font-size: 14px;
   opacity: 0.6;
}

/* show icon on hover or active */
.list .item.header p:hover i,
.list .item.header p.active i {
   opacity: 1;
}



</style>
