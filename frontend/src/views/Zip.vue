<template>
   <breadcrumbs :base="'/files'" :folderList="realFolderList" />

   <h4 class="listing-notice">{{ $t("files.zipArchiveMode") }} </h4>

   <breadcrumbs
      v-if="!searchActive"
      :base="'/zip/' + folderId + '/' + zipFileId"
      :folderList="zipFolderList"
   />
   <h4 v-if="!itemsError && searchActive && !itemsLoading">
      {{ $t("files.searchItemsFound", { amount: searchItems.length }) }}
   </h4>
   <errors v-if="itemsError" :error="itemsError" />

   <FileListing
      ref="listing"
      :headerButtons="headerButtons"
      :readonly="true"
      :minusSize="170"
      @download="download"
      @onOpen="onOpen"
      @openInNewWindow="openInNewWindow"
      @dropUpload="onDropUpload"
      @onSearchQuery="onSearchQuery"
   />

   <router-view />
</template>

<script>
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import Breadcrumbs from "@/components/listing/Breadcrumbs.vue"
import Errors from "@/components/Errors.vue"
import FileListing from "@/components/FileListing.vue"
import { humanTime, resolveItemAction } from "../utils/common.js"
import { getItems } from "@/api/folder.js"
import { smartDownload } from "@/utils/downloadUtils.js"

export default {
   name: "zip",

   components: { Errors, FileListing, Breadcrumbs },

   props: {
      folderId: { type: String, required: true },
      zipFileId: { type: String, required: true },
      zipPathId: { type: String, required: false, default: null }
   },

   data() {
      return {
         worker: null,
         realFolderList: [],
         zipFolderList: [],
         file: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["selected", "itemsLoading", "itemsError", "items", "selectedCount", "config", "breadcrumbs", "searchActive", "searchItems"]),

      headerButtons() {
         return {
            download: this.selectedCount === 1 && !this.selected[0].isDir,
            info: this.selectedCount > 0,
            search: true,
            advancedSearch: false
         }
      }
   },

   created() {
      document.title = "Archive viewer"
      this.setDisabledCreation(true)
      this.worker = new Worker(new URL("@/workers/zipWorker.js", import.meta.url), { type: "module" })
   },

   async mounted() {
      await this.init()
   },

   beforeUnmount() {
      if (this.worker) {
         this.worker.terminate()
         this.worker = null
      }

      this.setLastFile(this.file)
   },

   watch: {
      zipPathId() {
         this.loadList()
      }
   },

   methods: {
      humanTime,

      ...mapActions(useMainStore, ["setDisabledCreation", "setItems", "setSearchItems", "setCurrentFolderData",
         "setItemsLoading", "setItemsError", "setLastFile", "setSearchActive"]),

      async init() {
         try {
            this.setItemsLoading(true)

            if (!this.items?.length) {
               const res = await getItems(this.folderId)
               this.setCurrentFolderData(res)
            }

            this.realFolderList = this.breadcrumbs

            this.file = this.items.find(f => f.id === this.zipFileId)

            this.realFolderList.push({ name: this.file.name, id: this.file.parent_id })
            this.setLastFile(this.file)

            await this.sendWorker("init", { url: this.file.download_url, extensions: { ...this.config.extensions } })

            this.setItems(null)
            await this.loadList()
         } catch (error) {
            console.error(error)
            this.setItemsError(error)
         } finally {
            this.setItemsLoading(false)
         }
      },

      sendWorker(type, payload = {}) {
         return new Promise((resolve, reject) => {
            const handler = (e) => {
               if (e.data.type === "error") {
                  this.worker.removeEventListener("message", handler)
                  reject(e.data.error)
               }

               if (e.data.type === "ready" || e.data.type === "list" || e.data.type === "search") {
                  this.worker.removeEventListener("message", handler)
                  resolve(e.data)
               }
            }

            this.worker.addEventListener("message", handler)
            this.worker.postMessage({ type, payload })
         })
      },

      async loadList() {
         try {
            this.setItemsLoading(true)

            const res = await this.sendWorker("list", { fileId: this.zipPathId })

            this.setItems(res.items)

            this.zipFolderList = [
               { name: this.file.name, id: null, raw_path: null },
               ...res.breadcrumbs.map(item => ({ name: item.name, id: item.fileId, raw_path: item.raw_path }))
            ]
         } catch (error) {
            this.setItemsError(error)
         } finally {
            this.setItemsLoading(false)
         }
      },

      async onSearchQuery(searchParams) {
         try {
            this.setSearchActive(true)
            this.setItemsLoading(true)

            const res = await this.sendWorker("search", { query: searchParams.query })
            requestAnimationFrame(() => {
               this.setSearchItems(res.items) // this is vevy important
            })
         } catch (error) {
            this.setItemsError(error)
         } finally {
            this.setItemsLoading(false)
         }
      },

      getNewRoute(item) {
         const action = resolveItemAction(item)

         switch (action) {
            case "dir":
               return { name: "Zip", params: { folderId: this.folderId, zipFileId: this.zipFileId, zipPathId: item.fileId } }
            case "zip":
            case "preview":
               return { name: "ZipPreview", params: { folderId: this.folderId, zipFileId: this.zipFileId, zipPathId: this.zipPathId, fileId: item.fileId } }
         }
      },

      onOpen(item) {
         this.$router.replace(this.getNewRoute(item))
      },

      openInNewWindow(item) {
         const url = this.$router.resolve(this.getNewRoute(item)).href
         window.open(url, "_blank")
      },

      async download() {
         await smartDownload({ zipEntryDownload: true })
      },

      onDropUpload() {
         this.$toast.error(this.$t("toasts.uploadNotAllowedHere"))
      }
   }
}
</script>
<style scoped>
h4 {
   padding-left: 1em;
}
</style>