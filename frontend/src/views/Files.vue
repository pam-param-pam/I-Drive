<template>
  <div style="height: 100%">
    <breadcrumbs v-if="!searchActive" :folderList="breadcrumbs" base="/files" />
    <errors v-if="error" :error="error" />

    <h4 v-if="!error && searchActive && !loading">
      {{ $t("files.searchItemsFound", { amount: searchItems.length }) }}
    </h4>
    <FileListing
      ref="listing"
      :headerButtons="headerButtons"
      @download="download"
      @dragEnter="onDragEnter"
      @dragLeave="onDragLeave"
      @dropUpload="onDropUpload"
      @onOpen="onOpen"
      @onSearchClosed="onSearchClosed"
      @onSearchQuery="onSearchQuery"
      @openInNewWindow="openInNewWindow"
      @upload="upload"
      @uploadInput="onUploadInput"
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
import { cancelTokenMap } from "@/utils/networker.js"

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
         folderList: [],
         dragCounter: 0,
         isActive: true,
      }
   },

   computed: {
      ...mapState(useMainStore, ["searchItems", "searchFilters", "breadcrumbs", "error", "user", "settings", "loading", "selected", "perms", "selected", "currentFolder", "disabledCreation", "getFolderPassword", "selectedCount", "searchActive"]),
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
            lock: this.selectedCount === 1 && this.selected[0].isDir === true && this.perms.lock && this.perms.modify,
            locate: this.selectedCount === 1 && this.searchActive,
            search: true,
            openInNewWindow: true,
            modifyFile: this.selectedCount === 1 && !this.selected[0].isDir && this.perms.modify
         }
      }
   },

   created() {
      if (this.searchActive) {
         return
      }
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
      ...mapActions(useMainStore, ["setSearchFilters", "setSearchItems", "setCurrentFolderData", "setLoading", "setError", "setDisabledCreation", "setItems", "setCurrentFolder", "closeHover", "showHover", "setSearchActive"]),
      ...mapActions(useUploadStore, ["startUpload"]),

      async onSearchQuery(searchParams) {
         this.setLoading(true)
         let lockFrom = this.currentFolder?.lockFrom
         let password = this.getFolderPassword(lockFrom)
         try {
            this.setSearchActive(true)
            this.setDisabledCreation(true)
            let items = await search(searchParams, lockFrom, password)
            this.setSearchItems(items)
         } catch (error) {
            if (error.code === "ERR_CANCELED") return
            console.log(error)
            this.setError(error)

         } finally {
            this.setLoading(false)
         }
      },

      async onSearchClosed() {
         this.setSearchItems(null)
         this.setSearchActive(false)
         this.setDisabledCreation(false)
         this.setError(null)
         let searchRequest = cancelTokenMap.get("getItems")
         if (searchRequest) {
            searchRequest.cancel(
               `Request cancelled due to a new request with the same cancel signature .`
            )
         }
         let searchDict = { ...this.searchFilters }
         searchDict["query"] = ""
         this.setSearchFilters(searchDict)
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
         await this.onSearchClosed()

         if (this.currentFolder?.id === this.folderId) {
            this.folderList = this.currentFolder.breadcrumbs
         } else {
            try {
               this.setLoading(true)
               let res = await getItems(this.folderId, this.lockFrom)
               this.setCurrentFolderData(res)
            } catch (error) {
               if (error.code === "ERR_CANCELED") return
               console.log(error)
               this.setError(error)
            } finally {
               if (this.isActive) this.setLoading(false)
            }
         }
         //only set title if its not root folder and isn't locked
         if (this.currentFolder?.parent_id && !this.currentFolder.isLocked) {
            document.title = `${this.currentFolder.name} - ` + name
         } else {
            document.title = name
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

      async download() {
         if (this.selectedCount === 1 && !this.selected[0].isDir) {
            window.open(this.selected[0].download_url + "?download=true", "_blank")
            let message = this.$t("toasts.downloadingSingle", { name: this.selected[0].name })
            this.$toast.success(message)
         } else {
            const ids = this.selected.map((obj) => obj.id)
            let res = await createZIP({ ids: ids })
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
            return { name: 'Files', params: { folderId: item.id, lockFrom: item.lockFrom } }
         } else {
            if ((item.type === 'Text' || item.type === "Code") && item.size < 1024 * 1024) {
               return { name: 'Editor', params: { fileId: item.id, lockFrom: item.lockFrom } }
            } else {
               return { name: 'Preview', params: { fileId: item.id, lockFrom: item.lockFrom } }
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
         //if we are in search mode and we click to open a folder that we currently are in
         // routing won't work(as its already in that route, so we need to just quit the search)
         if (this.searchActive && item.id === this.currentFolder.id) {
            this.onSearchClosed()
            return
         }
         let route = this.getNewRoute(item)
         if (item.isDir) {
            if (item.isLocked === true) {
               let password = this.getFolderPassword(item.lockFrom)
               if (!password) {
                  this.showHover({
                     prompt: "FolderPassword",

                     props: { requiredFolderPasswords: [{ id: item.lockFrom, name: item.name }] },
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
<style scoped>
h4 {
 padding-left: 1em;
}
</style>
