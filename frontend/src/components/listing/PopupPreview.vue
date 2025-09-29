<template>
  <div class="popup-preview" v-if="source" ref="popup" :style="popupStyle">
    <img :src="source" alt="Popup image" :style="popupStyle">
  </div>
</template>

<script>

import { mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "PopupPreview",
   data() {
      return {
         popupStyle: {
            top: "0px",
            left: "0px"
         },
         showPopup: false,
         cursorX: 0,
         cursorY: 0
      }
   },
   watch: {
      source(newVal) {
         if (newVal) {
            this.popupStyle = { top: "0px", left: "0px" }
            this.$nextTick(() => {
               this.positionPopup()
            })
         }
      }
   },
   computed: {
      ...mapState(useMainStore, ["popupPreviewURL"]),
      source() {

         return this.popupPreviewURL
      }
   },
   mounted() {
      window.addEventListener("mousemove", this.updateCursorPosition)
   },
   beforeUnmount() {
      window.removeEventListener("mousemove", this.updateCursorPosition)
   },
   methods: {
      updateCursorPosition(event) {
         this.cursorX = event.clientX
         this.cursorY = event.clientY
         this.positionPopup()
      },
      positionPopup() {
         if (!this.source) return
         const popup = this.$refs.popup
         if (!popup) return

         const { innerWidth, innerHeight } = window
         const padding = 50

         const img = new Image()
         img.src = this.source

         img.onload = () => {
            let width = img.naturalWidth
            let height = img.naturalHeight

            // Determine scaling
            const maxDim = Math.max(width, height)

            if (maxDim < 700) {
               const scale = 700 / maxDim
               width *= scale
               height *= scale
            } else if (maxDim > 700) {
               const scale = 700 / maxDim
               width *= scale
               height *= scale
            }

            // Keep within viewport (optional)
            width = Math.min(width, innerWidth - 2 * padding)
            height = Math.min(height, innerHeight - 2 * padding)

            // Position centered on cursor
            let left = this.cursorX - width / 2
            let top = this.cursorY - height / 2

            left = Math.max(padding, Math.min(left, innerWidth - width - padding))
            top = Math.max(padding, Math.min(top, innerHeight - height - padding))

            this.popupStyle = {
               top: `${top}px`,
               left: `${left}px`,
               width: `${width}px`,
               height: `${height}px`,
               minWidth: `${width}px`,
               minHeight: `${height}px`,
               maxWidth: `${Math.min(width, 600)}px`,
               maxHeight: `${Math.min(height, 600)}px`,
               transform: "none",
               zIndex: "100000"
            }
         }
      }
   }
}
</script>

<style scoped>
.popup-preview {
 height: unset !important;
 position: fixed;
 pointer-events: none;
 border-radius: 1em;
 border-style: solid;
 border-width: 0.2em;
 box-shadow: 0 0 0.5em black;
 border-color: var(--dark-blue);
 overflow: hidden;
 z-index: 1000;
 transition: all 0.3s ease-in-out;
 background: gray;
}

.popup-preview img {
 pointer-events: none;
 width: auto;
 height: auto;
 max-width: 100%;
 max-height: 100%;
 display: block;
 object-fit: contain;

}
</style>