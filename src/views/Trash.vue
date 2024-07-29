<template>
  <div>
    <errors v-if="error" :errorCode="error.response.status"/>
    <h4 v-if="!error" class="listing-notice">{{$t('trash.info')}}</h4>
    <header-bar showMenu="false" showLogo="false">
      <title></title>

      <template #actions>
        <template v-if="!isMobile">
          <action
            v-if="headerButtons.delete"
            id="delete-button"
            icon="delete"
            :label="$t('buttons.delete')"
            show="delete"
          />
          <action
            v-if="headerButtons.restore"
            icon="restore"
            :label="$t('buttons.restoreFromTrash')"
            show="restoreFromTrash"
          />
        </template>
        <action
          v-if="headerButtons.shell"
          icon="code"
          :label="$t('buttons.shell')"
          @action="$store.commit('toggleShell')"
        />
        <action
          :icon="viewIcon"
          :label="$t('buttons.switchView')"
          @action="onSwitchView"
        />
        <action
          v-if="headerButtons.info"
          icon="info"
          :disabled="isSearchActive && !selectedCount > 0"
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
import {getTrash} from "@/api/user.js"
import HeaderBar from "@/components/header/HeaderBar.vue"
import Action from "@/components/header/Action.vue"
import Search from "@/components/Search.vue"

export default {
  name: "trash",
  components: {
    Search, Action, HeaderBar,
    Breadcrumbs,
    Errors,
    Listing,
  },

  data() {
    return {
      isSearchActive: false

    }
  },
  computed: {
    ...mapGetters(["selectedCount"]),
    ...mapState(["error", "items", "selected", "settings", "perms", "user", "loading", "currentFolder", "disabledCreation"]),
    headerButtons() {
      return {
        shell: this.perms.execute,
        info: this.selectedCount > 0,
        restore: this.selectedCount > 0 && this.perms.modify,
        delete: this.selectedCount > 0 && this.perms.delete,
      }
    },
    viewIcon() {
      const icons = {
        list: "view_module",
        mosaic: "grid_view",
        "mosaic gallery": "view_list",
      }
      return icons[this.settings.viewMode]
    },
    isMobile() {
      return this.width <= 950
    },

  },
  created() {
    this.setDisabledCreation(true)
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
    ...mapMutations(["updateUser", "addSelected", "resetSelected", "setLoading", "setError", "setDisabledCreation"]),

    async fetchFolder() {

      this.setLoading(true)
      this.setError(null)

      document.title = "Trash"

      let res = await getTrash()
      let items = res.trash
      this.$store.commit("setItems", items)

    },

    onSwitchView() {
      this.$refs.listing.switchView()
    },
    onOpen(item) {
      this.resetSelected()
      this.addSelected(item)
      this.$store.commit("showHover", "restoreFromTrash")
    }
  },
}
</script>
<style>

</style>