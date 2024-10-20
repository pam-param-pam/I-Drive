<template>
  <div>
    <breadcrumbs v-if="!isSearchActive"
                 base="/files"
                 :folderList="folderList"
    />
    <errors v-if="error" :errorCode="error.response?.status" />

    <h4 v-if="!error && isSearchActive && !loading">{{ $t("files.searchItemsFound", { amount: this.items.length }) }}</h4>
    <FileListing
      ref="listing"
      :locatedItem=locatedItem
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
    ></FileListing>
  </div>
</template>

<script>

import Breadcrumbs from "@/components/Breadcrumbs.vue"
import Errors from "@/views/Errors.vue"
import FileListing from "@/views/files/FileListing.vue"
import { getItems } from "@/api/folder.js"
import { name } from "@/utils/constants.js"
import { search } from "@/api/search.js"
import { checkFilesSizes } from "@/utils/upload.js"
import { createZIP } from "@/api/item.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { useUploadStore } from "@/stores/uploadStore.js"
import * as upload from "@/utils/upload.js"

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
      },
      locatedItem: {
         type: Object
      }

   },
   data() {
      return {
         items: [],
         isSearchActive: false,
         folderList: [],
         source: null,
         dragCounter: 0
      }
   },
   computed: {
      ...mapState(useMainStore, ["error", "user", "settings", "loading", "selected", "perms", "selected", "currentFolder", "disabledCreation", "getFolderPassword", "selectedCount"]),

      headerButtons() {
         return {
            info: !this.disabledCreation,
            shell: this.perms.execute,
            upload: this.perms.create,
            download: this.perms.download && this.selectedCount > 0,
            moveToTrash: this.selectedCount > 0 && this.perms.delete,
            modify: this.selectedCount === 1 && this.perms.modify,
            share: this.selectedCount === 1 && this.perms.share,
            lock: this.selectedCount === 1 && this.selected[0].isDir === true && this.perms.lock,
            locate: this.selectedCount === 1 && this.isSearchActive,
            search: true
         }
      }
   },
   created() {
      this.setDisabledCreation(false)

      this.fetchFolder()

   },
   renderTriggered({ key, target, type }) {
      console.log(`Render triggered on component 'Files'`, { key, target, type })
   },
   watch: {
      $route: "fetchFolder"
   },
   unmounted() {
      this.setItems(null)
      this.setCurrentFolder(null)

   },
   methods: {
      ...mapActions(useMainStore, ["setLoading", "setError", "setDisabledCreation", "setItems", "setCurrentFolder", "closeHover", "showHover"]),
      ...mapActions(useUploadStore, ["startUpload"]),

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
         console.log(dt.files)
         let el = event.target

         if (dt.files.length <= 0) return
         

         let parent_id = this.currentFolder.id

         //obtaining parent folder id
         for (let i = 0; i < 5; i++) {
            if (el !== null && !el.classList.contains("item")) {
               el = el.parentElement
            }
         }
         if (el !== null && el.classList.contains("item") && el.dataset.dir === "true") {
            parent_id = el.__vue__.item.id

         }
         console.log(parent_id)


         let files = await upload.scanFiles(dt)
         console.log("parent_id")
         console.log(parent_id)
         console.log("files")
         console.log(files)


      },
      async beginUpload(folder, files) {
         if (await checkFilesSizes(files)) {
            this.showHover({
               prompt: "NotOptimizedForSmallFiles",
               confirm: () => {
                  this.startUpload(files, folder)

               }
            })
         } else {
            this.startUpload(files, folder)

         }
      },
      async onUploadInput(event) {
         this.closeHover()

         let files = event.currentTarget.files
         let folder = this.currentFolder
         console.log(files)
         await this.beginUpload(folder, files)



      },
      locateItem() {
         this.$emit("onSearchClosed")
         let item = this.selected[0]
         let parent_id = item.parent_id

         this.$router.push({ name: "Files", params: { "folderId": "stupidAhHack" } })
         this.$router.push({ name: "Files", params: { "folderId": parent_id, "locatedItem": item } })

         let message = this.$t("toasts.itemLocated")
         this.$toast.info(message)


      },
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
         console.log(this.settings)
         if (!this.settings.webhook) {
            let message = this.$t("toasts.webhookMissing")
            this.$toast.error(message)
            return
         }

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

         this.searchItemsFound = null

         this.setError(null)
         this.setLoading(true)
         try {
           let res = await getItems(this.folderId, this.lockFrom)

           this.items = res.folder.children
           this.folderList = res.breadcrumbs

           this.setItems(this.items)
           this.setCurrentFolder(res.folder)

           if (res.parent_id) { //only set title if its not root folder
              document.title = `${res.name} - ` + name
           } else {
              document.title = name
           }
         } catch (error) {
            console.log(error)
            if (error.code === "ERR_CANCELED") return
            this.setError(error)
         } finally {
            this.setLoading(false)

         }

      },
      onOpen(item) {
         if (item.isDir) {
            if (item.isLocked === true) {
               let password = this.getFolderPassword(item.lockFrom)
               if (!password) {
                  this.showHover({
                     prompt: "FolderPassword",
                     //todo name should be lockfrom_name not just item _name
                     props: { requiredFolderPasswords: [{ "id": item.lockFrom, "name": item.name }] },
                     confirm: () => {
                        this.$router.push({ name: "Files", params: { "folderId": item.id, "lockFrom": item.lockFrom } })
                     }
                  })
                  return
               }
            }
            this.$router.push({ name: "Files", params: { "folderId": item.id, "lockFrom": item.lockFrom } })

         } else {

            if (item.type === "audio" || item.type === "video" || item.type === "image" || item.size >= 25 * 1024 * 1024 || item.extension === ".pdf" || item.extension === ".epub") {
               this.$router.push({ name: "Preview", params: { "fileId": item.id, "lockFrom": item.lockFrom } })

            } else {
               this.$router.push({ name: "Editor", params: { "fileId": item.id } })

            }

         }
      }
   }
}
</script>
