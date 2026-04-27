<template>
   <h4 class="listing-notice">{{ $t("trash.info") }}</h4>
   <errors v-if="error" :error="error" />

   <FileListing
      ref="listing"
      :headerButtons="headerButtons"
      :readonly="true"
      @dropUpload="onDropUpload"
      @onOpen="onOpen"
   ></FileListing>
</template>

<script>
import { getTrash } from "@/api/user.js"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { name } from "@/utils/constants"
import Errors from "@/components/Errors.vue"
import FileListing from "@/components/FileListing.vue"
import axios from "axios"

export default {
   name: "trash",

   components: {
      Errors,
      FileListing
   },


   computed: {
      ...mapState(useMainStore, ["itemsLoading", "itemsError", "items", "selected", "perms", "currentFolder", "disabledCreation", "selectedCount",
         "setSearchActive", "setSearchItems"]),

      headerButtons() {
         return {
            info: this.selectedCount > 0,
            restore: this.selectedCount > 0 && this.perms.modify,
            delete: this.selectedCount > 0 && this.perms.delete
         }
      }
   },

   unmounted() {
      this.isActive = false
      this.setItems(null)
   },

   mounted() {
      this.setItems(null)
      this.setDisabledCreation(true)
      this.setSearchActive(false)
      this.setSearchItems(null)
      this.fetchFolder()
   },

   methods: {
      ...mapActions(useMainStore, ["addSelected", "resetSelected", "setItemsLoading", "setItemsError", "setDisabledCreation", "setItems", "showHover"]),

      async fetchFolder() {
         document.title = this.$t("trash.trashName") + " - " + name

         this.setItemsError(null)
         this.setItemsLoading(true)

         try {
            let res = await getTrash()
            let items = res.trash
            this.setItems(items)
         } catch (error) {
            if (axios.isCancel(error)) return
            this.setItemsError(error)
         } finally {
            this.setItemsLoading(false)
         }
      },

      onOpen(item) {
         this.resetSelected()
         this.addSelected(item)
         this.showHover("restoreFromTrash")
      },
      onDropUpload() {
         this.$toast.error(this.$t("toasts.uploadNotAllowedHere"))
      }
   }
}
</script>
