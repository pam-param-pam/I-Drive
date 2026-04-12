<template>
   <object
      :data="inlineSrc"
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

   emits: ["previewEvent", "error"],
   computed: {
      inlineSrc() {
         if (!this.src) return ""

         return this.src.includes("?")
            ? `${this.src}&inline=true`
            : `${this.src}?inline=true`
      }
   },
   methods: {
      ...mapActions(useMainStore, ["setTextError"]),
      onError(e) {
         this.$emit("Failed to load pdf file")
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