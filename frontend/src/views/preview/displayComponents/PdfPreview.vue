<template>
   <object
      :data="inlineSrc"
      class="pdf"
      @error="onError"
   ></object>
</template>

<script>
import { getFileRawData } from "@/api/files.js"

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
      onError(e) {
         console.log(e)
         this.$emit("error", "Failed to load pdf file")
         getFileRawData(this.src, { responseType: "arraybuffer" })
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