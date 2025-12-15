<template>
  <div
    class="file-input-wrapper"
    :class="{ 'drag-over': isDragOver }"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent="onDragOver"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <input
      ref="input"
      type="file"
      :accept="accept"
      @change="onFileSelect"
    />
    <label class="file-label" @click="triggerFileDialog">
      {{ fileName || label }}
    </label>
  </div>
</template>

<script>
export default {
   name: "SmartFileInput",
   props: {
      accept: { type: String, default: "" },
      label: { type: String, default: "" }
   },
   emits: ["file-selected"],
   data() {
      return {
         isDragOver: false,
         fileName: ""
      }
   },
   methods: {
      triggerFileDialog() {
         this.$refs.input.click()
      },
      onFileSelect(e) {
         let file = e.target.files[0]
         this.handleFile(file)
      },
      handleFile(file) {
         if (!file) return

         if (this.isFileAccepted(file)) {
            this.fileName = file.name
            this.$emit("file-selected", file)
         } else {
            this.$toast.error(this.$t("toasts.invalidFileFormat"))
         }
      },
      reset() {
         this.$refs.input.value = null
         this.fileName = ""
      },
      isFileAccepted(file) {
         if (!this.accept) return true

         const accepted = this.accept.split(",").map(a => a.trim().toLowerCase())

         const fileName = file.name.toLowerCase()
         const fileType = (file.type || "").toLowerCase()

         return accepted.some(rule => {
            if (!rule) return false

            if (rule.startsWith(".")) {
               return fileName.endsWith(rule)
            }

            if (rule.endsWith("/*")) {
               const baseType = rule.slice(0, rule.indexOf("/"))
               return fileType.startsWith(baseType + "/")
            }

            if (rule.includes("/")) {
               return fileType === rule
            }

            return false
         })
      },
      onDragEnter() {
         this.isDragOver = true
      },
      onDragOver() {
         this.isDragOver = true
      },
      onDragLeave(e) {
         if (!e.currentTarget.contains(e.relatedTarget)) {
            this.isDragOver = false
         }
      },
      onDrop(e) {
         this.isDragOver = false
         const file = e.dataTransfer.files[0]
         this.handleFile(file)
      }
   }
}
</script>

<style scoped>
.file-input-wrapper {
 position: relative;
 display: flex;
 align-items: center;
 width: 100%;
 justify-content: center;
}

input[type="file"] {
 opacity: 0;
 width: 0;
 height: 0;
 position: absolute;
}

.file-label {
 display: inline-block;
 padding: 10px 15px;
 background-color: var(--divider);
 color: var(--textPrimary);
 border-radius: 5px;
 cursor: pointer;
 text-align: center;
 width: 100%;
 font-size: 14px;
 transition: background-color 0.2s ease, border 0.2s ease;
 border: 2px dashed transparent;
 margin-top: 2em;
}

.file-input-wrapper.drag-over .file-label {
 background-color: rgba(128, 128, 128, 0.1);
 border-color: var(--accent, #4da3ff);
}
</style>
