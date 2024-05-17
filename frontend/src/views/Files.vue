<template>
  <div>
    <header-bar v-if="error" showMenu showLogo />

    <errors v-if="error" :errorCode="error.status"/>
    <breadcrumbs v-if="!isSearchActive && !error" base="/files"/>
    <h4 v-else-if="!error">{{$t('files.searchItemsFound', {amount: this.items.length})}}</h4>
    <Listing
      :isTrash="false"
      :isSearchActive="isSearchActive"
      @onSearchClosed="onSearchClosed"
      @onSearchQuery="onSearchQuery"
    ></Listing>
  </div>
</template>

<script>
import {mapMutations, mapState} from "vuex";

import Breadcrumbs from "@/components/Breadcrumbs.vue";
import Errors from "@/views/Errors.vue";
import Listing from "@/views/files/Listing.vue";
import {getItems} from "@/api/folder.js";
import {name} from "@/utils/constants.js";
import {search} from "@/api/search.js";
import HeaderBar from "@/components/header/HeaderBar.vue";

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

  },
  data: function () {
    return {
      items: [],
      isSearchActive: false
    };
  },
  computed: {
    ...mapState(["error", "user"]),

  },
  created() {
    this.fetchFolder()

  },
  watch: {
    $route: "fetchFolder",
  },
  destroyed() {
    this.$store.commit("setItems", null);
    this.$store.commit("setCurrentFolder", null);

  },
  methods: {
    ...mapMutations(["updateUser", "addSelected", "setLoading", "setError"]),

    async onSearchClosed() {
      this.isSearchActive = false
      await this.fetchFolder()
    },

    async onSearchQuery(query) {
      this.isSearchActive = true
      this.items = await search(query)
      this.$store.commit("setItems", this.items);
      this.$store.commit("setCurrentFolder", null);

    },
    async fetchFolder() {

      this.searchItemsFound = null

      this.setLoading(true);
      this.setError(null)

      try {
        let res = await getItems(this.folderId, false);
        this.items = res.children
        this.$store.commit("setItems", this.items);
        this.$store.commit("setCurrentFolder", res);

        if (res.parent_id) { //only set title if its not root folder
          document.title = `${res.name} - ` + name;
        }
        else {
          document.title = name;
        }

      } catch (error) {
        this.setError(error);

        if (error.status === 469) {
          this.$store.commit("showHover", {
            prompt: "FolderPassword",
            props: {folderId: this.folderId},
            confirm: () => {
              this.fetchFolder();

            },
          });
        }
      } finally {
        this.setLoading(false);

      }

    },
  },
};
</script>
