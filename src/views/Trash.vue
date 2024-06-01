<template>
  <div>
    <errors v-if="error" :errorCode="error.status"/>
    <h4 v-if="!error">{{$t('trash.info', {amount: this.items.length})}}</h4>

    <Listing
      :isTrash="true"
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
import {getTrash} from "@/api/user.js"

export default {
  name: "trash",
  components: {
    Breadcrumbs,
    Errors,
    Listing,
  },

  data: function () {
    return {
      items: [],
      isSearchActive: false

    }
  },
  computed: {
    ...mapState(["error", "user"]),

  },
  created() {
    this.setDisableCreation(true)
    this.fetchFolder()

  },
  watch: {
    $route: "fetchFolder",
  },
  beforeDestroy() {
    this.$store.commit("setItems", null)
    this.$store.commit("setCurrentFolder", null)


  },

  methods: {
    ...mapMutations(["updateUser", "addSelected", "setLoading", "setError", "setDisableCreation"]),
    async onSearchClosed() {
      //this.isSearchActive = false
      //await this.fetchFolder()
    },

    async onSearchQuery(query) {
      //this.items = await search(query)

    },
    async fetchFolder() {

      this.setLoading(true)
      this.setError(null)

      try {
        let res = await getTrash()
        this.items = res.trash
        this.$store.commit("setItems", this.items)

      } catch (error) {
        this.setError(error)

      } finally {
        document.title = "Trash"
        this.setLoading(false)
      }
    },
  },
}
</script>
