<template>
  <div class="wrapper">
    <header-bar>

      <Search
        ref="search"
        v-if="headerButtons.search"
        @onSearchQuery="(query) => $emit('onSearchQuery', query)"
        @exit="$emit('onSearchClosed')"
      />
      <title></title>
      <template #actions>
        <template v-if="!isMobile()">
          <action
            v-if="headerButtons.locate"
            icon="location_on"
            :label="$t('buttons.locate')"
            @action="locateItem"
          />
          <action
            v-if="headerButtons.tag"
            id="tag"
            icon="sell"
            :label="$t('buttons.editTags')"
            show="EditTags"
          />
          <action
            v-if="headerButtons.share"
            icon="share"
            :label="$t('buttons.share')"
            show="share"
          />
          <action
            v-if="headerButtons.modify"
            icon="mode_edit"
            :label="$t('buttons.rename')"
            show="rename"
          />
          <action
            v-if="headerButtons.move"
            id="move-button"
            icon="forward"
            :label="$t('buttons.moveFile')"
            show="move"
          />
          <action
            v-if="headerButtons.moveToTrash"
            id="moveToTrash-button"
            icon="delete"
            :label="$t('buttons.moveToTrash')"
            show="moveToTrash"
          />
          <action
            v-if="headerButtons.restore"
            icon="restore"
            :label="$t('buttons.restoreFromTrash')"
            show="restoreFromTrash"
          />
          <action
            v-if="headerButtons.delete"
            id="delete-button"
            icon="delete_forever"
            :label="$t('buttons.delete')"
            show="delete"
          />


        </template>
        <action
          v-if="headerButtons.lock"
          icon="lock"
          :label="$t('buttons.lockFolder')"
          show="editFolderPassword"
        />
        <action
          v-if="headerButtons.download"
          icon="file_download"
          :label="$t('buttons.download')"
          @action="$emit('download')"
          :counter="selectedCount"
        />
        <action
          v-if="headerButtons.upload"
          :disabled="searchActive && !selectedCount > 0 "
          icon="file_upload"
          id="upload-button"
          :label="$t('buttons.upload')"
          @action="$emit('upload')"
        />
        <action
          v-if="headerButtons.shell"
          icon="code"
          :label="$t('buttons.shell')"
          @action="toggleShell()"
        />
        <action
          :icon="viewIcon"
          :label="$t('buttons.switchView')"
          @action="switchView"
        />
        <action
          v-if="headerButtons.info"
          icon="info"
          :disabled="searchActive && !selectedCount > 0"
          :label="$t('buttons.info')"
          show="info"
        />
      </template>

    </header-bar>
    <loading-spinner />

    <template v-if="!error && !loading">

      <div v-if="sortedItems?.length === 0">
        <h2 class="message">
          <a href="https://www.youtube.com/watch?app=desktop&v=nGBYEUNKPmo">
            <img
              src="/img/youLookLonelyICanFixThat.jpg"
              :alt="$t('files.noFiles')">
          </a>
        </h2>
        <input
          style="display: none"
          type="file"
          id="upload-input"
          @change="uploadInput($event)"
          multiple
        />
        <input
          style="display: none"
          type="file"
          id="upload-folder-input"
          @change="uploadInput($event)"
          webkitdirectory
          multiple
        />
      </div>
      <div v-else class="wrapper">
        <div
          :class="viewMode + ' file-icons'"
          @dragenter.prevent @dragover.prevent
        >


          <div class="item header">
            <div>
              <p
                :class="{ active: nameSorted }"
                class="nameSort"
                role="button"
                tabindex="0"
                @click="sort('name')"
                :title="$t('files.sortByName')"
                :aria-label="$t('files.sortByName')"
              >
                <span>{{ $t("files.name") }}</span>
                <i class="material-icons">{{ nameIcon }}</i>
              </p>

              <p
                :class="{ active: sizeSorted }"
                class="sizeSort"
                role="button"
                tabindex="0"
                @click="sort('size')"
                :title="$t('files.sortBySize')"
                :aria-label="$t('files.sortBySize')"
              >
                <span>{{ $t("files.size") }}</span>
                <i class="material-icons">{{ sizeIcon }}</i>
              </p>

              <p
                :class="{ active: createdSorted }"
                class="createdSort"
                role="button"
                tabindex="0"
                @click="sort('created')"
                :title="$t('files.sortByCreated')"
                :aria-label="$t('files.sortByCreated')"
              >
                <span>{{ $t("files.created") }}</span>
                <i class="material-icons">{{ createdIcon }}</i>
              </p>
            </div>
          </div>


          <RecycleScroller
            ref="filesScroller"
            id="filesScroller"
            class="scroller"
            :style="scrollerClass"
            :items="sortedItems"
            :item-size="tileHeight"
            :grid-items="gridItems"
            :prerender="400"
            :item-secondary-size="tileWidth"
            v-slot="{ item }"
          >
            <item
              :item="item"
              :readOnly="readonly"
              :ref="item.id"
              :key="item.id"
              :imageWidth="imageWidth"
              :imageHeight="imageHeight"
              :tileHeight="tileHeight"
              :tileWidth="tileWidth"
              @onOpen="$emit('onOpen', item)"
              @onLongPress="showContextMenu($event, item)"
              @contextmenu.prevent="showContextMenu($event, item)"
            >
            </item>

          </RecycleScroller>


          <input
            style="display: none"
            type="file"
            id="upload-input"
            @change="uploadInput($event)"
            multiple
          />
          <input
            style="display: none"
            type="file"
            id="upload-folder-input"
            @change="uploadInput($event)"
            webkitdirectory
            multiple
          />

        </div>
      </div>

      <context-menu
        :show="contextMenuState.visible"
        :pos="contextMenuState.pos"
        @hide="hideContextMenu"
      >
        <action
          v-if="headerButtons.locate"
          icon="location_on"
          :label="$t('buttons.locate')"
          @action="locateItem"
        />
        <action
          v-if="headerButtons.openInNewWindow && selected[0]?.isDir"
          icon="open_in_new"
          :label="$t('buttons.openFolder')"
          @action="$emit('openInNewWindow', selected[0])"
        />
        <action
          v-if="headerButtons.openInNewWindow && !selected[0]?.isDir"
          icon="open_in_new"
          :label="$t('buttons.openFile')"
          @action="$emit('openInNewWindow', selected[0])"
        />
        <action icon="info" :label="$t('buttons.info')" show="info" />

        <action
          v-if="headerButtons.modify"
          icon="mode_edit"
          :label="$t('buttons.rename')"
          show="rename"
        />
        <action
          v-if="headerButtons.moveToTrash"
          id="moveToTrash-button"
          icon="delete"
          :label="$t('buttons.moveToTrash')"
          show="moveToTrash"
        />
        <action
          v-if="headerButtons.restore"
          icon="restore"
          :label="$t('buttons.restoreFromTrash')"
          show="restoreFromTrash"
        />
        <action
          v-if="headerButtons.delete"
          id="delete-button"
          icon="delete_forever"
          :label="$t('buttons.delete')"
          show="delete"
        />
        <action
          v-if="headerButtons.move"
          id="move-button"
          icon="forward"
          :label="$t('buttons.moveFile')"
          show="move"
        />
        <action
          v-if="headerButtons.download"
          icon="file_download"
          :label="$t('buttons.download')"
          @action="$emit('download')"
        />
        <action
          v-if="headerButtons.share"
          icon="share"
          :label="$t('buttons.share')"
          show="share"
        />
        <action
          v-if="headerButtons.lock"
          icon="lock"
          :label="$t('buttons.lockFolder')"
          show="editFolderPassword"
        />
        <action
          v-if="headerButtons.copyShare"
          icon="content_copy"
          :label="$t('buttons.copyFileShareUrl')"
          @action="$emit('copyFileShareUrl')"
        />
        <action
          v-show="headerButtons.tag && contextMenuState.advanced"
          id="tag"
          icon="sell"
          :label="$t('buttons.editTags')"
          show="EditTags"
        />
        <action
          v-show="headerButtons.tag && contextMenuState.advanced && this.selected[0].type === 'video'"
          id="thumbnail"
          icon="image"
          :label="$t('buttons.editThumbnail')"
          show="EditThumbnail"
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

export default {
   name: "FileListing",
   components: {
      Search, HeaderBar,
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
         columnWidth: 280,
         dragCounter: 0,
         itemWeight: 0,
         searchItemsFound: null,
         contextMenuState: {"visible": false},

         //experimental
         tileWidth: 40,
         tileHeight: 75,
         imageHeight: 100,
         imageWidth: 100,
         numberOfTiles: 4,

         scrollInterval: null
      }
   },
   watch: {
      items() {
         // Ensures that the listing is displayed
         this.$nextTick(() => {
            this.calculateGridLayoutWrapper()
            this.scrollToLastItem()
         })
      }

   },

   mounted() {

      this.$nextTick(() => {

         this.calculateGridLayoutWrapper()
         this.scrollToLastItem()
      })
      //
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
   beforeUnmount() {
      this.resetSelected()

      if (this.scrollToAnimationTimeout) {
         clearTimeout(this.scrollToAnimationTimeout)
         this.scrollToAnimationTimeout = null
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
      ...mapState(useMainStore, ["sortedItems", "lastItem", "items", "settings", "perms", "user", "selected", "loading", "error", "currentFolder", "selectedCount", "isLogged", "currentPrompt", "searchActive"]),
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
            "list": "view_module",
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
      isMobile,

      ...mapActions(useMainStore, ["setSelected", "setLastItem", "toggleShell", "addSelected", "setItems", "resetSelected", "showHover", "setSortByAsc", "setSortingBy", "updateSettings"]),

      async uploadInput(event) {
         this.$emit("uploadInput", event)
      },
      showContextMenu(event, item) {
         this.resetSelected()
         this.addSelected(item)
         let advanced = event.ctrlKey || event.shiftKey

         let max_x_size = 200
         let max_y_size = 400

         let posX = event.clientX + 30
         let posY = event.clientY - 40

         if (advanced) max_y_size = 450

         const viewportWidth = window.innerWidth
         const viewportHeight = window.innerHeight

         if ((posX + max_x_size) > viewportWidth) {
            posX = viewportWidth - max_x_size
         }

         if ((posY + max_y_size) > viewportHeight) {
            posY = viewportHeight - max_y_size
         }

         this.contextMenuState.pos = {
            x: posX,
            y: posY
         }

         this.contextMenuState.visible = true
         this.contextMenuState.advanced = advanced

      },
      hideContextMenu() {
         this.contextMenuState.visible = false
         this.contextMenuState.advanced = false
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
            this.hideContextMenu()
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
         if ((event.ctrlKey || event.metaKey) && !this.searchActive) {

            let key = String.fromCharCode(event.which).toLowerCase()

            if (key === "a") {
               event.preventDefault()
               this.setSelected(this.items)
            }
         }
      },

      dragEnter() {
         this.$emit("dragEnter")
      },

      dragLeave() {
         this.$emit("dragLeave")
      },

      preventDefault(event) {
         event.preventDefault()
      },

      async drop(event) {
         if (!this.currentFolder || this.isSearchActive) {
            event.preventDefault()
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
               filesScroller.scrollBy({ top: scrollSpeed})
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
         await updateSettings({ "sortingBy": by, "sortByAsc": asc })

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
         this.$router.push({ name: "Files", params: { "folderId": parent_id } })

         this.hideContextMenu()
      },

      async switchView() {
         let modes = {
            "list": "width grid",
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
         if (this.viewMode !== "grid") return

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
         } else {
            this.tileWidth = tileWidth
            this.tileHeight = tileWidth * 1.5
         }

         this.imageHeight = this.tileHeight - 65
         if (isMobile()) this.imageHeight += 20

      },

      scrollToLastItem() {
         if (!this.lastItem) return
         let filesScroller = this.$refs.filesScroller
         let index = this.sortedItems.findIndex(file => file.id === this.lastItem.id) - this.numberOfTiles
         let lastItemId = this.lastItem.id

         setTimeout(() => {
            filesScroller.scrollToItem(index)

            setTimeout(() => {
               let itemElement = this.$refs[lastItemId]
               if (itemElement) {
                  itemElement.$el.classList.add("pulse-animation")

                  // Remove the animation class after 3.5 seconds
                  this.scrollToAnimationTimeout = setTimeout(() => {
                     itemElement.$el.classList.remove("pulse-animation")
                     this.setLastItem(null)
                     this.scrollToAnimationTimeout = null
                  }, 3500)
               }
            }, 100)

         }, 50)
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

</style>