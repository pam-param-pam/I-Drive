<template>
   <breadcrumbs :base="'/files'" :folderList="realFolderList" />

   <h4 class="listing-notice">{{ $t("files.zipArchiveMode") }} </h4>

   <breadcrumbs
     :base="'/zip/' + folderId + '/' + zipFileId"
     :folderList="zipFolderList"
   />

   <errors v-if="itemsError" :error="itemsError" />

   <FileListing
     ref="listing"
     :headerButtons="headerButtons"
     :readonly="true"
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
import { humanTime } from "../utils/common.js"
import { getItems } from "@/api/folder.js"
import { nextTick } from "vue"
import { search } from "@/api/search.js"
import axios from "axios"

export default {
   name: "zip",

   components: {
      Errors,
      FileListing,
      Breadcrumbs
   },

   props: {
      folderId: { type: String, required: true },
      zipFileId: { type: String, required: true },
      path: { type: String, required: false }
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
      ...mapState(useMainStore, ["selected", "itemsLoading", "itemsError", "items", "selectedCount", "config", "breadcrumbs"]),

      headerButtons() {
         return {
            download: this.selectedCount === 1 && !this.selected[0].isDir,
            info: this.selectedCount > 0,
            search: true,
            advancedSearch: false
         }
      }
   },

   async created() {
      document.title = "Archive viewer"
      this.setDisabledCreation(true)

      this.worker = new Worker(new URL("@/workers/zipWorker.js", import.meta.url), { type: "module" })

      this.worker.onmessage = this.handleWorkerMessage

   },
   async mounted() {
      await this.init()
   },
   beforeUnmount() {
      if (this.worker) {
         this.worker.terminate()
         this.worker = null
      }
   },

   watch: {
      "$route.params.path"() {
         this.loadList()
      }
   },

   methods: {
      humanTime,

      ...mapActions(useMainStore, ["setDisabledCreation", "setItems", "setSearchItems", "setCurrentFolderData", "setItemsLoading", "setItemsError", "setLastItem"]),

      // -------------------------
      // INIT
      // -------------------------
      async onSearchQuery(searchParams) {
         this.setItemsLoading(true)
         try {
            const query = searchParams.query

            const res = await this.sendWorker("search", { query })
            this.setSearchItems(res.items)
         } catch (error) {
            this.setItemsError(error)
         } finally {
            this.setItemsLoading(false)
         }
      },
      async init() {
         try {
            this.setItemsLoading(true)

            if (this.items.length === 0) {
               const res = await getItems(this.folderId)
               this.setCurrentFolderData(res)
            }

            this.realFolderList = this.breadcrumbs

            this.file = this.items.find(f => f.id === this.zipFileId)

            this.realFolderList.push({name: this.file?.name, id: this.file.parent_id})
            this.setLastItem(this.file)

            await this.sendWorker("init", {url: this.file.download_url, extensions: {...this.config.extensions}})

            this.setItems(null)
            await this.loadList()

         } catch (e) {
            console.error(e)
            this.setItemsError(e)
         } finally {
            this.setItemsLoading(false)
         }
      },

      // -------------------------
      // WORKER COMMUNICATION
      // -------------------------
      sendWorker(type, payload) {
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
         await this.sendWorker("list", {
            path: this.path || ""
         })
      },

      async handleWorkerMessage(e) {
         if (e.data.type === "list") {
            let items = e.data.items
            requestAnimationFrame(() => { // vevy important
               this.setItems(items)
            })

            this.zipFolderList = this.buildBreadcrumbs(this.path)
         }

         if (e.data.type === "search") {
            const items = e.data.items

            requestAnimationFrame(() => { // keep same rendering behavior
               this.setSearchItems(items)
            })

            return
         }

         if (e.data.type === "error") {
            this.setItemsError(e.data.error)
         }
      },

      // -------------------------
      // NAVIGATION
      // -------------------------
      getNewRoute(item) {
         if (item.isDir) {
            return {
               name: "Zip",
               params: { ...this.$route.params, path: item.id }
            }
         } else {
            return {
               name: "ZipPreview",
               params: { ...this.$route.params, fileId: item.id }
            }
         }
      },

      onOpen(item) {
         this.$router.replace(this.getNewRoute(item))
      },

      openInNewWindow(item) {
         const url = this.$router.resolve(this.getNewRoute(item)).href
         window.open(url, "_blank")
      },

      // -------------------------
      // DOWNLOAD
      // -------------------------
      async download() {
         if (this.selectedCount === 1 && !this.selected[0].isDir) {
            const url = this.selected[0].download_url
            if (url) window.open(url, "_blank")
         }
      },

      // -------------------------
      // BREADCRUMBS
      // -------------------------
      buildBreadcrumbs(folderId) {
         if (!folderId) return []

         const parts = folderId.split("/").filter(Boolean)

         return parts.map((part, i) => ({
            name: part,
            id: parts.slice(0, i + 1).join("/")
         }))
      },
      onDropUpload() {
         this.$toast.error(this.$t("toasts.uploadNotAllowedHere"))
      }
   }
}
</script>