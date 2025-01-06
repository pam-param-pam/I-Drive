<template>
  <h4 v-if="shareState === 'error'" class="listing-notice">{{ $t("share.shareNotFound") }}</h4>

  <h4 v-if="shareState === 'success'" class="listing-notice">
    {{ $t("share.info", { expiry: humanExpiry(expiry) }) }}</h4>

  <breadcrumbs
    v-if="shareState === 'success'"
    :base="'/share/' + token"
    :folderList="folderList"
  />
  <errors v-if="error" :error="error" />

  <FileListing
    ref="listing"
    :isSearchActive="false"
    :readonly="true"
    :headerButtons="headerButtons"
    @onOpen="onOpen"
    @download="download"
    @openInNewWindow="openInNewWindow"
    @copyFileShareUrl="copyFileShareUrl"
  ></FileListing>

</template>

<script>

import { createShareZIP, getShare } from "@/api/share.js"
import moment from "moment/min/moment-with-locales.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import Breadcrumbs from "@/components/listing/Breadcrumbs.vue"
import Errors from "@/components/Errors.vue"
import FileListing from "@/components/FileListing.vue"


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
         shareState: "fetching"

      }
   },
   computed: {
      ...mapState(useMainStore, ["selected", "loading", "error", "disabledCreation", "settings", "selectedCount", "isLogged"]),

      headerButtons() {
         return {
            download: this.selectedCount > 0,
            info: this.selectedCount > 0,
            openInNewWindow: true,
            copyShare: this.selectedCount === 1,
         }
      },


   },
   created() {
      document.title = "share"

      this.setDisabledCreation(true)
      this.fetchShare()
   },

   watch: {
      $route: "fetchShare"
   },

   methods: {
      ...mapActions(useMainStore, ["setLoading", "setError", "setDisabledCreation", "setItems", "getFolderPassword"]),
      async download() {
         if (this.selectedCount === 1 && !this.selected[0].isDir) {
            window.open(this.selected[0].download_url, "_blank")
            let message = this.$t("toasts.downloadingSingle", { name: this.selected[0].name })
            this.$toast.success(message)

         } else {
            const ids = this.selected.map(obj => obj.id)
            let res = await createShareZIP(this.token, { "ids": ids })
            window.open(res.download_url, "_blank")

            let message = this.$t("toasts.downloadingZIP")
            this.$toast.success(message)

         }
      },
      getNewRoute(item) {
         if (item.isDir) {
            return { name: "Share", params: { "token": this.token, "folderId": item.id } }
         } else {
            if (item.type === "text" && item.size < 1024 * 1024) {
               return { name: "ShareEditor", params: { "folderId": item.parent_id, "fileId": item.id, "token": this.token } }
            } else {
               return { name: "SharePreview", params: { "folderId": item.parent_id, "fileId": item.id, "token": this.token } }
            }
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
         this.$toast.success(this.$t("toasts.linkCopied"))
         navigator.clipboard.writeText(url);
      },
      async fetchShare() {
         this.setLoading(true)
         try {
            let res = await getShare(this.token, this.folderId)

            this.shareObj = res
            this.folderList = res.breadcrumbs
            this.expiry = res.expiry
            this.id = res.id

            this.setItems(res.share)
            this.shareState = "success"

         } catch (e) {
            console.log(e)
            this.shareState = "error"
            this.setItems(null)
            this.setError(e)

         }
         finally {
            this.setLoading(false)
         }


      },
      humanExpiry(date) {
         //todo czm globalny local nie działa?
         let locale = this.settings?.locale || "en"

         moment.locale(locale)

         // Parse the target date
         return moment(date, "YYYY-MM-DD HH:mm").endOf("second").fromNow()

      }


   }
}
</script>
