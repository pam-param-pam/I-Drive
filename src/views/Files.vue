<template>
  <div>
    <header-bar v-if="error" showMenu showLogo />

    <errors v-if="error" :errorCode="error.status"/>
    <breadcrumbs v-if="!isSearchActive && !error"
       base="/files"
      :folderList="folderList"
    />

    <h4 v-else-if="!error">{{$t('files.searchItemsFound', {amount: this.items.length})}}</h4>
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
    }
  },
  computed: {
    ...mapState(["error", "user"]),

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
      this.isSearchActive = true
      this.items = await search(query)
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
