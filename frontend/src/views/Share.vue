<template>
  <div>
    <h4 v-if="shareState === 'error'" class="listing-notice">{{ $t('share.shareNotFound') }}</h4>

    <h4 v-if="shareState === 'success'" class="listing-notice">
      {{ $t('share.info', {expiry: humanExpiry(expiry)}) }}</h4>

    <breadcrumbs
      v-if="shareState === 'success'"
      :base="'/share/' + token"
      :folderList="folderList"
    />

    <FileListing
      ref="listing"
      :isSearchActive="false"
      :readonly="true"
      :headerButtons="headerButtons"
      @onOpen="onOpen"

    ></FileListing>
    <errors v-if="shareState === 'passwordRequired'" :errorCode="error.response?.status"/>


  </div>
</template>

<script>

import Breadcrumbs from "@/components/Breadcrumbs.vue"
import {getShare} from "@/api/share.js"
import {createZIP} from "@/api/item.js"
import moment from "moment/min/moment-with-locales.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"
import FileListing from "@/views/files/FileListing.vue"
import Errors from "@/views/Errors.vue";

export default {
   name: "files",
   components: {
      Errors,
      FileListing,
      Breadcrumbs,
   },

   props: {
      token: {
         type: String,
         required: true,
      },
      folderId: {
         type: String,
      }
   },

   data() {
      return {
         items: [],
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
            info: this.selectedCount > 0
         }
      }

   },
   created() {
      document.title = "share"

      //if anonymous user, we need to set state like locale or viewMode etc
      if (!this.isLogged) {
         this.setAnonState()
      }

      this.setDisabledCreation(true)
      this.fetchShare()
   },

   watch: {
      $route: "fetchShare",

   },


   methods: {
      ...mapActions(useMainStore, ["setLoading", "setError", "setDisabledCreation", "setAnonState", "setItems"]),

      async download() {
         console.log(this.selectedCount)
         if (this.selectedCount === 1 && !this.selected[0].isDir) {
            window.open(this.selected[0].download_url, '_blank')
            let message = this.$t("toasts.downloadingSingle", {name: this.selected[0].name})
            this.$toast.success(message)

         } else {
            const ids = this.selected.map(obj => obj.id)
            let res = await createZIP({"ids": ids})
            window.open(res.download_url, '_blank')

            let message = this.$t("toasts.downloadingZIP")
            this.$toast.success(message)

         }
      },

      onOpen(item) {
         if (item.isDir) {
            this.$router.push({name: "Share", params: {"token": this.token, "folderId": item.id}})

         } else {
            if (item.type === "audio" || item.type === "video" || item.type === "image" || item.size >= 25 * 1024 * 1024 || item.extension === ".pdf" || item.extension === ".epub") {
               this.$router.push({
                  name: "SharePreview",
                  params: {"folderId": item.parent_id, "fileId": item.id, "token": this.token}
               })

            } else {
               this.$router.push({
                  name: "ShareEditor",
                  params: {"folderId": item.parent_id, "fileId": item.id, "token": this.token}
               })

            }
         }

      },

      async fetchShare() {

      try {
         let res = await getShare(this.token, this.folderId)

         this.shareObj = res
         this.items = res.share
         this.folderList = res.breadcrumbs
         this.expiry = res.expiry
         this.setItems(this.items)
         this.shareState = 'success'
      }
         finally {

      }


      },

      humanExpiry(date) {
         //todo czm globalny local nie działa?
         let locale = this.settings?.locale || "en"

         moment.locale(locale)

         // Parse the target date
         return moment(date, "YYYY-MM-DD HH:mm").endOf('second').fromNow()

      },

   },
}
</script>
