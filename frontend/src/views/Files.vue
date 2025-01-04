<template>
  <div style="height: 100%">
    <breadcrumbs v-if="!isSearchActive"
                 base="/files"
                 :folderList="breadcrumbs"
    />
    <errors v-if="error" :error="error" />

    <h4 v-if="!error && isSearchActive && !loading">{{ $t("files.searchItemsFound", { amount: this.items.length }) }}</h4>
    <FileListing
      ref="listing"
      :isSearchActive="isSearchActive"
      :headerButtons="headerButtons"
      @onOpen="onOpen"
      @dragEnter="onDragEnter"
      @dragLeave="onDragLeave"
      @uploadInput="onUploadInput"
      @onSearchClosed="onSearchClosed"
      @onSearchQuery="onSearchQuery"
      @upload="upload"
      @download="download"
      @dropUpload="onDropUpload"
      @openInNewWindow="openInNewWindow"

    ></FileListing>
  </div>
</template>

<script>



import { getItems } from "@/api/folder.js"
import { search } from "@/api/search.js"
import { createZIP } from "@/api/item.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { useUploadStore } from "@/stores/uploadStore.js"
import { scanDataTransfer } from "@/utils/uploadHelper.js"
import { uploadType } from "@/utils/constants.js"
import { name } from "@/utils/constants"
import Breadcrumbs from "@/components/listing/Breadcrumbs.vue"
import Errors from "@/components/Errors.vue"
import FileListing from "@/components/FileListing.vue"

export default {
   name: "files",
   components: {
      Breadcrumbs,
      Errors,
      FileListing
   },

   props: {
      folderId: {
         type: String,
         required: true
      },
      lockFrom: {
         type: String
      }

   },
   data() {
      return {
         items: [],
         isSearchActive: false,
         folderList: [],
         source: null,
         dragCounter: 0,
         isActive: true,
      }
   },
   computed: {
      ...mapState(useMainStore, ["breadcrumbs", "error", "user", "settings", "loading", "selected", "perms", "selected", "currentFolder", "disabledCreation", "getFolderPassword", "selectedCount"]),
      headerButtons() {
         return {
            info: !this.disabledCreation,
            shell: this.perms.execute,
            upload: this.perms.create && this.currentFolder,
            download: this.perms.download && this.selectedCount > 0,
            moveToTrash: this.selectedCount > 0 && this.perms.delete,
            modify: this.selectedCount === 1 && this.perms.modify,
            move: this.selectedCount >= 1 && this.perms.modify,
            share: this.selectedCount === 1 && this.perms.share,
            lock: this.selectedCount === 1 && this.selected[0].isDir === true && this.perms.lock,
            locate: this.selectedCount === 1 && this.isSearchActive,
            search: true,
            openInNewWindow: true
         }
      }
   },
   created() {
      this.setDisabledCreation(false)
      this.fetchFolder()
   },
   unmounted() {
      this.isActive = false
   },
   watch: {
      $route: "fetchFolder"
   },
   methods: {
      ...mapActions(useMainStore, ["setCurrentFolderData", "setLoading", "setError", "setDisabledCreation", "setItems", "setCurrentFolder", "closeHover", "showHover"]),
      ...mapActions(useUploadStore, ["startUpload"]),

      async onSearchQuery(query) {
         this.setLoading(true)

         let realLockFrom = this.lockFrom || this.folderId
         let password = this.getFolderPassword(realLockFrom)
         try {
            this.items = await search(query, realLockFrom, password)
            this.isSearchActive = true
            this.setCurrentFolder(null)
            this.setItems(this.items)

         } catch (error) {
            if (error.code === "ERR_CANCELED") return
            this.setError(error)
         } finally {
            this.setLoading(false)

         }

      },
      upload() {

         if (
            typeof window.DataTransferItem !== "undefined" &&
            typeof DataTransferItem.prototype.webkitGetAsEntry !== "undefined"
         ) {
            this.showHover("upload")
         } else {
            document.getElementById("upload-input").click()
         }
      },

      async fetchFolder() {
         this.isSearchActive = false
         this.setError(null)

         this.searchItemsFound = null

         if (this.currentFolder?.id === this.folderId) {
            this.folderList = this.currentFolder.breadcrumbs

         } else {
            try {
               this.setLoading(true)
               let res = await getItems(this.folderId, this.lockFrom)
               this.setCurrentFolderData(res)

            } catch (error) {
               console.log(error)
               if (error.code === "ERR_CANCELED") return
               this.setError(error)
            } finally {
               if (this.isActive) this.setLoading(false)

            }
         }
         if (this.currentFolder.parent_id) { //only set title if its not root folder
            document.title = `${this.currentFolder.name} - ` + name
         }


      },
      onDragEnter() {
         this.dragCounter++

         // When the user starts dragging an item, put every
         // file on the listing with 50% opacity.
         let items = document.getElementsByClassName("item")

         Array.from(items).forEach((file) => {
            file.style.opacity = 0.5
         })
      },
      onDragLeave() {

         this.dragCounter--

         if (this.dragCounter === 0) {
            this.resetOpacity()
         }
      },
      async onSearchClosed() {
         if (this.source) {
            this.source.cancel("Cancelled previous request")
         }

         await this.fetchFolder()
         //todo this breaks shit up with locateItem. possibly race condition, this call  finishes after locateItem

      },
      async download() {
         console.log(this.selectedCount)
         if (this.selectedCount === 1 && !this.selected[0].isDir) {
            window.open(this.selected[0].download_url, "_blank")
            let message = this.$t("toasts.downloadingSingle", { name: this.selected[0].name })
            this.$toast.success(message)

         } else {
            const ids = this.selected.map(obj => obj.id)
            let res = await createZIP({ "ids": ids })
            window.open(res.download_url, "_blank")

            let message = this.$t("toasts.downloadingZIP")
            this.$toast.success(message)


         }
      },
      resetOpacity() {
         let items = document.getElementsByClassName("item")

         Array.from(items).forEach((file) => {
            file.style.opacity = 1
         })
      },
      async onDropUpload(event) {
         event.preventDefault()

         this.dragCounter = 0
         this.resetOpacity()


         let dt = event.dataTransfer
         let el = event.target

         if (dt.files.length <= 0) return

         let folderContextId = this.currentFolder.id

         //obtaining parent folder id
         for (let i = 0; i < 5; i++) {
            if (el !== null && !el.classList.contains("item")) {
               el = el.parentElement
            }
         }
         if (el !== null && el.classList.contains("item") && el.dataset.dir === "true") {
            folderContextId = el.dataset.id
         }
         let files = await scanDataTransfer(dt)

         await this.startUpload(uploadType.dragAndDropInput, folderContextId, files)


      },

      async onUploadInput(event) {
         this.closeHover()

         let files = event.currentTarget.files
         let folderContextId = this.currentFolder.id
         await this.startUpload(uploadType.browserInput, folderContextId, files)


      },
      getNewRoute(item) {
         if (item.isDir) {
            return { name: "Files", params: { "folderId": item.id, "lockFrom": item.lockFrom } }
         } else {
            if (item.type === "text" && item.size < 1024 * 1024) {
               return { name: "Editor", params: { "fileId": item.id, "lockFrom": item.lockFrom } }
            } else {
               return { name: "Preview", params: { "fileId": item.id, "lockFrom": item.lockFrom } }
            }
         }
      },
      openInNewWindow(item) {
         let route = this.getNewRoute(item)
         let url = this.$router.resolve(route).href
         window.open(url, "_blank")

      },
      onOpen(item) {
         this.$refs.listing.hideContextMenu()
         let route = this.getNewRoute(item)
         if (item.isDir) {
            if (item.isLocked === true) {
               let password = this.getFolderPassword(item.lockFrom)
               if (!password) {
                  this.showHover({
                     prompt: "FolderPassword",

                     props: { requiredFolderPasswords: [{ "id": item.lockFrom, "name": item.name }] },
                     confirm: () => {
                        this.$router.push(route)
                     }
                  })
                  return
               }
            }
         }
         this.$router.push(route)
      }
   }
}
</script>
<style>
h4 {
 padding-left: 1em;
}
</style>
