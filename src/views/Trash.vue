<template>
  <div>
    <errors v-if="error" :errorCode="error.response.status"/>
    <h4 v-if="!error" class="listing-notice">{{ $t('trash.info') }}</h4>
    <header-bar>
      <title></title>

      <template #actions>
        <template v-if="!isMobile()">
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
          @action="toggleShell()"
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
    <FileListing
      ref="listing"
      :isSearchActive="false"
      @onOpen="onOpen"
      :readonly="true"

    ></FileListing>
  </div>
</template>

<script>

import Errors from "@/views/Errors.vue"
import {getTrash} from "@/api/user.js"
import HeaderBar from "@/components/header/HeaderBar.vue"
import Action from "@/components/header/Action.vue"
import {isMobile} from "@/utils/common.js"
import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"
import FileListing from "@/views/files/FileListing.vue"

export default {
   name: "trash",
   components: {
      Action,
      HeaderBar,
      Errors,
      FileListing,
   },

   data() {
      return {
         isSearchActive: false

      }
   },
   computed: {
      ...mapState(useMainStore, ["error", "items", "selected", "settings", "perms", "loading", "currentFolder", "disabledCreation", "selectedCount"]),
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

   },
   created() {
      this.setDisabledCreation(true)
      this.fetchFolder()
      console.log(this.headerButtons)
   },
   watch: {
      $route: "fetchFolder",
   },
   beforeUnmount() {
      this.setItems(null)
      this.setCurrentFolder(null)

   },

   methods: {
      isMobile,
      ...mapActions(useMainStore, ["toggleShell", "addSelected", "resetSelected", "setLoading", "setError", "setDisabledCreation", "setItems", "setCurrentFolder", "showHover"]),

      async fetchFolder() {

         this.setLoading(true)
         this.setError(null)

         document.title = "Trash"

         let res = await getTrash()
         let items = res.trash
         this.setItems(items)

      },

      onSwitchView() {
         this.$refs.listing.switchView()
      },
      onOpen(item) {
         this.resetSelected()
         this.addSelected(item)
         this.showHover("restoreFromTrash")
      }
   },
}
</script>
<style>

</style>