<template>

  <errors v-if="error" :error="error"/>
  <h4 v-if="!error" class="listing-notice">{{ $t('trash.info') }}</h4>

  <FileListing
    ref="listing"
    :isSearchActive="false"
    :readonly="true"
    :headerButtons="headerButtons"
    @onOpen="onOpen"

  ></FileListing>

</template>

<script>

import {getTrash} from "@/api/user.js"
import {mapActions, mapState} from "pinia"
import {useMainStore} from "@/stores/mainStore.js"
import {name} from "@/utils/constants"
import Errors from "@/components/Errors.vue"
import FileListing from "@/components/FileListing.vue"

export default {
   name: "trash",
   components: {
      Errors,
      FileListing,
   },

   data() {
      return {
         isSearchActive: false,
         isActive: true,

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
   unmounted() {
      this.isActive = false
   },
   created() {
      this.setDisabledCreation(true)
      this.fetchFolder()
   },
   watch: {
      $route: "fetchFolder",
   },
   mounted() {
      this.setItems(null)
      this.setCurrentFolder(null)

   },

   methods: {
      ...mapActions(useMainStore, ["addSelected", "resetSelected", "setLoading", "setError", "setDisabledCreation", "setItems", "setCurrentFolder", "showHover"]),

      async fetchFolder() {
         document.title = this.$t("trash.trashName") + " - " + name

         this.setError(null)
         this.setLoading(true)

         try {
            let res = await getTrash()
            let items = res.trash
            this.setItems(items)

         }
         catch (error) {
            if (error.code === "ERR_CANCELED") return
            this.setError(error)
         }
         finally {
            if (this.isActive) this.setLoading(false)

         }

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