<template>
   <h4 v-if="shareState === 'error'" class="listing-notice">{{ $t("share.shareNotFound") }}</h4>

   <h4 v-if="shareState === 'success'" class="listing-notice">
      {{ $t("share.info", { expiry: humanTime(expiry) }) }}
   </h4>

   <breadcrumbs v-if="shareState === 'success'" :base="'/share/' + token" :folderList="folderList"/>
   <errors v-if="itemsError" :error="itemsError" />

   <FileListing
      ref="listing"
      :headerButtons="headerButtons"
      :readonly="true"
      @copyFileShareUrl="copyFileShareUrl"
      @download="download"
      @onOpen="onOpen"
      @openInNewWindow="openInNewWindow"
   ></FileListing>
   <router-view />

</template>

<script>
import { createShareZIP, getShare } from "@/api/share.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import Breadcrumbs from "@/components/listing/Breadcrumbs.vue"
import Errors from "@/components/Errors.vue"
import FileListing from "@/components/FileListing.vue"
import { humanTime, resolveItemAction } from "../utils/common.js"

export default {
   name: "files",

   components: {
      Errors,
      FileListing,
      Breadcrumbs
   },

   props: {
      token: {
         type: String,
         required: true
      },
      folderId: {
         type: String
      }
   },

   data() {
      return {
         folderList: [],
         expiry: null,
         shareObj: {},
         shareState: "fetching",
         loading: false,
         error: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["itemsLoading", "itemsError", "selected", "disabledCreation", "settings", "selectedCount", "isLogged"]),

      headerButtons() {
         return {
            download: this.selectedCount > 0,
            info: this.selectedCount > 0,
            openInNewWindow: this.selectedCount === 1,
            copyShare: this.selectedCount === 1 && !this.selected[0].isDir
         }
      }
   },

   created() {
      document.title = "share"

      this.setDisabledCreation(true)
      this.fetchShare()
   },

   watch: {
      '$route.params.folderId'() {
         this.fetchShare()
      }
   },

   methods: {
      humanTime,
      ...mapActions(useMainStore, ["setItemsLoading", "setItemsError", "setDisabledCreation", "setItems", "getFolderPassword"]),

      async download() {
         if (this.selectedCount === 1 && !this.selected[0].isDir) {
            window.open(this.selected[0].download_url + "?download=true", "_blank")
            let message = this.$t("toasts.downloadingSingle", { name: this.selected[0].name })
            this.$toast.success(message)
         } else {
            const ids = this.selected.map((obj) => obj.id)
            let res = await createShareZIP(this.token, { ids: ids })
            window.open(res.download_url, "_blank")

            let message = this.$t("toasts.downloadingZIP")
            this.$toast.success(message)
         }
      },

      getNewRoute(item) {
         const action = resolveItemAction(item)

         switch (action) {
            case "dir":
               return { name: "Share", params: { ...this.$route.params, folderId: item.id }}
            case "zip":
               return {name: "SharePreview", params: { ...this.$route.params, fileId: item.id }}
               // return { name: "Zip", params: { folderId: item.parent_id || "aa", zipFileId: item.id }}
            case "preview":
               return {name: "SharePreview", params: { ...this.$route.params, fileId: item.id }}
         }
      },

      openInNewWindow(item) {
         let route = this.getNewRoute(item)
         let url = this.$router.resolve(route).href
         window.open(url, "_blank")
      },

      onOpen(item) {
         let route = this.getNewRoute(item)
         this.$router.push(route)
      },

      copyFileShareUrl() {
         let url = this.selected[0].download_url + "?inline=True"
         navigator.clipboard.writeText(url)
         this.$toast.success(this.$t("toasts.linkCopied"))

      },

      async fetchShare() {
         this.setItemsError(null)
         try {
            this.setItemsLoading(true)
            let res = await getShare(this.token, this.folderId)

            this.shareObj = res
            this.folderList = res.breadcrumbs
            this.expiry = res.expiry
            this.id = res.id

            this.setItems(res.share)
            this.shareState = "success"
         } catch (e) {
            this.shareState = "error"
            this.setItemsError(e)
         } finally {
            this.setItemsLoading(false)
         }
      }

   }
}
</script>
