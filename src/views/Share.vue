<template>
  <div>
    <h4 v-if="!isShareValid" class="listing-notice">{{$t('share.shareNotFound')}}</h4>

    <h4 v-if="isShareValid && !this.loading" class="listing-notice">{{$t('share.info', {expiry: humanExpiry(expiry)})}}</h4>

    <breadcrumbs
      v-if="isShareValid && !this.loading"
      :base="'/share/' + token"
      :folderList="folderList"
    />

    <header-bar>

    <title/>
    <template #actions>

      <action
        icon="file_download"
        :label="$t('buttons.download')"
        @action="download"
        :counter="selectedCount"
      />
      <action
        :icon="viewIcon"
        :label="$t('buttons.switchView')"
        @action="onSwitchView"
      />
      <action
        v-if="selectedCount > 0"
        icon="info"
        :disabled="!selectedCount > 0"
        :label="$t('buttons.info')"
        show="info"
      />

    </template>
    </header-bar>

    <Listing
      ref="listing"
      :isSearchActive="false"
      @onOpen="onOpen"
      :readonly="true"

    ></Listing>


  </div>
</template>

<script>
import {mapGetters, mapMutations, mapState} from "vuex"

import Breadcrumbs from "@/components/Breadcrumbs.vue"
import Errors from "@/views/Errors.vue"
import Listing from "@/views/files/Listing.vue"
import HeaderBar from "@/components/header/HeaderBar.vue"
import {getShare} from "@/api/share.js"
import Action from "@/components/header/Action.vue"
import {createZIP} from "@/api/item.js"
import moment from "moment/min/moment-with-locales.js"

export default {
  name: "files",
  components: {
    Breadcrumbs,
    Action,
    HeaderBar,
    Errors,
    Listing,
  },
  props: {
    token: String,
    folderId: String,

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

    ...mapState(["selected", "loading", "error", "disabledCreation", "settings"]),
    ...mapGetters(["selectedCount", "currentPrompt", "isLogged"]),

    isShareValid() {
      return !this.shareErrored
    },
    viewIcon() {
      const icons = {
        list: "view_module",
        mosaic: "grid_view",
        "mosaic gallery": "view_list",
      }
      return icons[this.settings.viewMode]
    },

  },
  created() {

    //if anonymous user, we need to set state like locale or viewMode etc
    if (!this.isLogged) {
      this.$store.commit("setAnonState")

    }

    this.setDisabledCreation(true)
    this.fetchShare()
  },

  watch: {
    $route: "fetchShare",

  },



  methods: {
    ...mapMutations(["setLoading", "setError", "setDisabledCreation"]),

    async download() {
      console.log(this.selectedCount)
      if (this.selectedCount === 1 && !this.selected[0].isDir) {
        window.open(this.selected[0].download_url, '_blank')
        let message = this.$t("toasts.downloadingSingle", {name: this.selected[0].name})
        this.$toast.success(message)

      }
      else {
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

      }

    else {
        if (item.type === "audio" || item.type === "video" || item.type === "image" ||  item.size >= 25 * 1024 * 1024 || item.extension === ".pdf" || item.extension === ".epub") {
          this.$router.push({name: "SharePreview", params: {"folderId": item.parent_id, "fileId":item.id, "token": this.token}} )

        }
        else {
          this.$router.push({name: "ShareEditor", params: {"folderId": item.parent_id, "fileId":item.id, "token": this.token}} )

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
        this.$store.commit("setItems", this.items)

      } catch {
        this.shareErrored = true
        //todo networked bullshit with seterror and setloaidng uh
      } finally {
        this.setLoading(false)
        document.title = "share"

      }
    },

    onSwitchView() {
      this.$refs.listing.switchView()
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
