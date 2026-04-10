<template>
   <CorePreview
      :file="file"
      :isInShareContext="false"
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
      ...mapState(useMainStore, ["items"]),
      file() {
         return this.items.find(f => f.id === this.fileId)
      }
   },
   methods: {
      ...mapActions(useMainStore, ["addSelected"]),
      onClose() {
         this.$router.push({ name: "Zip", params: { ...this.$route.params } })
      }
   }
}
</script>