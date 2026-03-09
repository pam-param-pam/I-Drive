<template>
  <div class="office-preview">
    <div v-if="loading" class="loading">Loading...</div>

    <div
      v-else-if="isDocx"
      class="docx-preview"
      v-html="docxHtml"
    ></div>

    <div v-else class="unsupported">
      <p>Unsupported file type.</p>
    </div>
  </div>
</template>

<script>
import { renderAsync } from 'docx-preview'
import { isMobile } from "@/utils/common.js"
import { getFileRawData } from "@/api/files.js"
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: 'OfficePreview',
   props: {
      file: {
         type: Object,
         required: true
      },
      fileUrl: {
         type: String,
         required: true
      }
   },
   data() {
      return {
         docxHtml: '',
         excelHtml: '',
         loading: true
      }
   },
   computed: {
      isDocx() {
         return this.file.name.endsWith('.docx')
      },
   },
   async mounted() {
      if (this.isDocx) {
         await this.renderDocx()
      }
      this.loading = false
   },
   methods: {
      ...mapActions(useMainStore, ["setError"]),
      async renderDocx() {
         try {
            let data = await getFileRawData(this.fileUrl, { responseType: 'arraybuffer' })
            let container = document.createElement('div')

            await renderAsync(data, container, null,{
               ignoreWidth: isMobile(),
               inWrapper: true,
            })
            this.docxHtml = container.innerHTML
         }
         catch (error) {
            console.error(error)
            this.setError(error)
         }

      },
   }
}
</script>

<style scoped>
.office-preview {
 max-height: 95vh;
 overflow: auto;
 max-width: 100%;
 font-family: sans-serif;
}

</style>
