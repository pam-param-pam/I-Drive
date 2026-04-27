<template>
   <div style="height: 100%">
      <breadcrumbs v-if="!searchActive" :folderList="breadcrumbs" base="/files" />
      <errors v-if="itemsError" :error="itemsError" />

      <h4 v-if="!itemsError && searchActive && !itemsLoading">
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
         @onSearchQuery="onSearchQuery"
         @openInNewWindow="openInNewWindow"
         @upload="upload"
         @uploadInput="onUploadInput"
      ></FileListing>
      <router-view/>
   </div>
</template>

<script>
import { getItems } from "@/api/folder.js"
import { search } from "@/api/search.js"
import { createZIP } from "@/api/item.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { scanDataTransfer } from "@/upload/utils/uploadHelper.js"
import { uploadType } from "@/utils/constants.js"
import { name } from "@/utils/constants"
import Breadcrumbs from "@/components/listing/Breadcrumbs.vue"
import Errors from "@/components/Errors.vue"
import FileListing from "@/components/FileListing.vue"
import { getUploader } from "@/upload/Uploader.js"
import axios from "axios"
import { resolveItemAction } from "@/utils/common.js"
import HeaderBar from "@/components/header/HeaderBar.vue"
import Search from "@/components/Search.vue"

export default {
   name: "files",

   components: {
      Search, HeaderBar,
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
         dragCounter: 0
      }
   },

   computed: {
      ...mapState(useMainStore, ["itemsLoading", "itemsError", "currentPrompt", "searchItems", "breadcrumbs", "user", "selected", "perms", "selected",
         "currentFolder", "disabledCreation", "getFolderPassword", "selectedCount", "searchActive"]),

      headerButtons() {
         return {
            info: !this.disabledCreation || this.selectedCount > 0,
            upload: this.perms.create && this.currentFolder && !this.searchActive,
            download: this.perms.download && this.selectedCount > 0,
            moveToTrash: this.selectedCount > 0 && this.perms.delete,
            modify: this.selectedCount === 1 && this.perms.modify,
            move: this.selectedCount >= 1 && this.perms.modify,
            share: this.selectedCount === 1 && this.perms.share,
            lock: this.selectedCount === 1 && this.selected[0].isDir === true && this.perms.lock && this.perms.modify,
            locate: this.selectedCount === 1 && this.searchActive,
            search: true,
            advancedSearch: true,
            openInNewWindow: this.selectedCount === 1,
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

   watch: {
      "$route.params.folderId"() {
         this.fetchFolder()
      }

   },

   methods: {
      ...mapActions(useMainStore, ["setLastFolder", "setItemsLoading", "setItemsError", "setSearchItems", "setCurrentFolderData", "setDisabledCreation",
         "setCurrentFolder", "closeHover", "showHover"]),

      async onSearchQuery(searchParams) {
         this.setItemsLoading(true)
         try {
            let lockFrom = this.currentFolder?.lockFrom
            let password = this.getFolderPassword(lockFrom)
            let items = await search(searchParams, lockFrom, password)
            this.setSearchItems(items)
         } catch (error) {
            if (axios.isCancel(error)) return
            this.setItemsError(error)
         } finally {
            this.setItemsLoading(false)
         }
      },

      upload() {
         if (typeof window.DataTransferItem !== "undefined" && typeof DataTransferItem.prototype.webkitGetAsEntry !== "undefined") {
            this.showHover("upload")
         } else {
            document.getElementById("upload-input").click()
         }
      },

      async fetchFolder() {
         await this.$refs?.listing?.$refs?.search?.exit()

         if (this.currentFolder?.id === this.folderId && this.items) {
            this.folderList = this.currentFolder.breadcrumbs
         } else {
            try {
               this.setItemsLoading(true)
               let res = await getItems(this.folderId, this.lockFrom)
               this.setCurrentFolderData(res)
            } catch (error) {
               if (axios.isCancel(error)) return
               console.log(error)
               this.setItemsError(error)
            } finally {
               this.setItemsLoading(false)
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
         if (this.currentPrompt) return
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
         if (this.currentPrompt) return

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

         await getUploader().startUploadWithChecks(uploadType.dragAndDropInput, folderContextId, files)
      },

      async onUploadInput(event) {
         this.closeHover()

         let files = event.currentTarget.files
         let folderContextId = this.currentFolder.id
         await getUploader().startUploadWithChecks(uploadType.browserInput, folderContextId, files)
      },

      getNewRoute(item) {
         const action = resolveItemAction(item)

         switch (action) {
            case "dir":
               return { name: "Files", params: { folderId: item.id, lockFrom: item.lockFrom } }
            case "zip":
               return { name: "Zip", params: { folderId: item.parent_id, zipFileId: item.id } }
            case "preview":
               return { name: "Preview", params: { ...this.$route.params, fileId: item.id } }
         }
      },

      openInNewWindow(item) {
         let route = this.getNewRoute(item)
         let url = this.$router.resolve(route).href
         window.open(url, "_blank")
      },

      onOpen(item) {
         //if we are in search mode and we click to open a folder that we currently are in
         // routing won't work(as its already in that route, so we need to just quit the search)
         if (this.searchActive && item.id === this.currentFolder.id) {
            this.$refs?.listing?.$refs?.search?.exit()
            return
         }
         let route = this.getNewRoute(item)
         //todo
         if (item.isLocked === true) {
            let password = this.getFolderPassword(item.lockFrom)
            if (!password) {
               this.showHover({
                  prompt: "FolderPassword",

                  props: { requiredFolderPasswords: [{ id: item.lockFrom, name: item.name }] },
                  confirm: () => {
                     this.$router.replace(route)
                  }
               })
               return
            }
         }

         this.$router.replace(route)
      }
   }
}
</script>
<style scoped>
h4 {
  padding-left: 1em;
}
</style>
