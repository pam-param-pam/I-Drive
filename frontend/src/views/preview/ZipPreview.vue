<template>
   <CorePreview
      :file="file"
      :readonly="true"
      :headerButtons="headerButtons"
      source="zip"
      @close="onClose"
   />
</template>

<script>

import CorePreview from "@/views/preview/CorePreview.vue"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   components: { CorePreview },
   props: {
      fileId: String,
   },
   data() {
      return {
         headerButtons: {
            download: true,
            modify: false,
            delete: false
         }
      }
   },
   watch: {
      file: {
         immediate: true,
         async handler(file) {
            if (!file) return
            this.addSelected(file)
         }
      }
   },
   computed: {
      ...mapState(useMainStore, ["sortedItems"]),
      file() {
         return this.sortedItems.find(f => f.id === this.fileId)
      }
   },
   methods: {
      ...mapActions(useMainStore, ["addSelected", "setLastItem"]),
      onClose() {
         this.$router.replace({ name: "Zip", params: { ...this.$route.params } })
      }
   }
}
</script>