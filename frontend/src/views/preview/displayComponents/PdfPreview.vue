<template>
   <object
      :data="src"
      class="pdf"
      @error="onError"
   ></object>
</template>

<script>
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "PdfPreview",

   props: {
      file: {
         type: Object,
         required: true
      },
      src: {
         type: String,
         required: true
      }
   },

   emits: ["error"],

   methods: {
      ...mapActions(useMainStore, ["setTextError"]),
      onError(e) {
         this.setTextError(500, "Failed to load pdf file. Reason unknown")

      }
   }
}
</script>

<style scoped>
.pdf {
  width: 100%;
  height: 100%;
}
</style>