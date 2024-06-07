<template>
  <div>
    <header-bar v-if="error" showMenu showLogo />
    <breadcrumbs v-if="!isSearchActive"
                 base="/files"
                 :folderList="folderList"
    />
    <errors v-if="error" :errorCode="error.response.status"/>


    <h4 v-if="!error && isSearchActive && !loading">{{$t('files.searchItemsFound', {amount: this.items.length})}}</h4>
    <Listing
      :isTrash="false"
      :isShares="false"
      :isSearchActive="isSearchActive"
      @onSearchClosed="onSearchClosed"
      @onSearchQuery="onSearchQuery"
    ></Listing>
  </div>
</template>

<script>
import {mapMutations, mapState} from "vuex"

import Breadcrumbs from "@/components/Breadcrumbs.vue"
import Errors from "@/views/Errors.vue"
import Listing from "@/views/files/Listing.vue"
import {getItems} from "@/api/folder.js"
import {name} from "@/utils/constants.js"
import {search} from "@/api/search.js"
import HeaderBar from "@/components/header/HeaderBar.vue"
import axios from "axios"

export default {
  name: "files",
  components: {
    HeaderBar,
    Breadcrumbs,
    Errors,
    Listing,
  },
  props: {
    folderId: String,
    lockFrom: String,

  },
  data: function () {
    return {
      items: [],
      isSearchActive: false,
      folderList: [],
      source: null,

    }
  },
  computed: {
    ...mapState(["error", "user", "loading"]),

  },
  created() {
    this.setDisableCreation(false)

    this.fetchFolder()

  },
  watch: {
    $route: "fetchFolder",
  },
  destroyed() {
    this.$store.commit("setItems", null)
    this.$store.commit("setCurrentFolder", null)

  },
  methods: {
    ...mapMutations(["updateUser", "addSelected", "setLoading", "setError", "setDisableCreation"]),

    async onSearchClosed() {
      this.isSearchActive = false
      await this.fetchFolder()
    },

    async onSearchQuery(query) {
      this.setLoading(true)

      if (this.source) {
        this.source.cancel('Cancelled previous request')
      }
      this.source = axios.CancelToken.source()

      this.items = await search(query, this.source)
      this.setLoading(false)
      this.isSearchActive = true
      this.$store.commit("setItems", this.items)
      this.$store.commit("setCurrentFolder", null)

    },
    async fetchFolder() {
      this.isSearchActive = false

      this.searchItemsFound = null

      this.setLoading(true)
      this.setError(null)

      try {
        let res = await getItems(this.folderId, this.lockFrom)
        console.log(res)
        this.items = res.folder.children
        this.folderList = res.breadcrumbs
        this.$store.commit("setItems", this.items)
        this.$store.commit("setCurrentFolder", res.folder)


        if (res.parent_id) { //only set title if its not root folder
          document.title = `${res.name} - ` + name
        }
        else {
          document.title = name
        }

      } catch (error) {
        this.setError(error)


      } finally {
        this.setLoading(false)

      }

    },
  },
}
</script>
