<template>
  <div>
    <h4 v-if="!isShareValid" class="listing-notice">{{ $t('share.shareNotFound') }}</h4>

    <h4 v-if="isShareValid && !this.loading" class="listing-notice">
      {{ $t('share.info', {expiry: humanExpiry(expiry)}) }}</h4>

    <breadcrumbs
      v-if="isShareValid && !this.loading"
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


  </div>
</template>

<script>

import Breadcrumbs from "@/components/Breadcrumbs.vue"
import HeaderBar from "@/components/header/HeaderBar.vue"
import {getShare} from "@/api/share.js"
import Action from "@/components/header/Action.vue"
import {createZIP} from "@/api/item.js"
import moment from "moment/min/moment-with-locales.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"
import FileListing from "@/views/files/FileListing.vue"

export default {
   name: "files",
   components: {
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
         shareErrored: false

      }
   },
   computed: {
      ...mapState(useMainStore, ["selected", "loading", "error", "disabledCreation", "settings", "selectedCount", "isLogged"]),

      isShareValid() {
         return !this.shareErrored
      },
      headerButtons() {
         return {
            download: this.selectedCount > 0,
            info:  this.selectedCount > 0
         }
      }

   },
   created() {

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

         this.setLoading(true)
         this.setError(null)

         try {
            let res = await getShare(this.token, this.folderId)
            this.shareObj = res
            this.items = res.share
            this.folderList = res.breadcrumbs
            this.expiry = res.expiry
            this.setItems(this.items)

         } catch {
            this.shareErrored = true
            //todo networked bullshit with seterror and setloaidng uh
         } finally {
            this.setLoading(false)
            document.title = "share"
            //todo share i18n name

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
