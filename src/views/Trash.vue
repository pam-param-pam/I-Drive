<template>
  <div>
    <errors v-if="error" :errorCode="error.response.status"/>
    <h4 v-if="!error" class="listing-notice">{{ $t('trash.info') }}</h4>

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
      Errors,
      FileListing,
   },

   data() {
      return {
         isSearchActive: false

      }
   },
   computed: {
      ...mapState(useMainStore, ["error", "items", "selected", "perms", "loading", "currentFolder", "disabledCreation", "selectedCount"]),
      headerButtons() {
         return {
            shell: this.perms.execute,
            info: this.selectedCount > 0,
            restore: this.selectedCount > 0 && this.perms.modify,
            delete: this.selectedCount > 0 && this.perms.delete,
         }
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
      ...mapActions(useMainStore, ["addSelected", "resetSelected", "setLoading", "setError", "setDisabledCreation", "setItems", "setCurrentFolder", "showHover"]),

      async fetchFolder() {

         this.setLoading(true)
         this.setError(null)

         document.title = "Trash"

         let res = await getTrash()
         let items = res.trash
         this.setItems(items)

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