<template>
   <div class="popup-preview" v-if="source" ref="popup" :style="popupStyle">
      <img :src="source" alt="Popup image" :style="popupStyle">
   </div>
</template>

<script>

import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "PopupPreview",
   data() {
      return {
         popupStyle: {
            top: "0px",
            left: "0px"
         },
         cursorX: 0,
         cursorY: 0,
         oldSource: null
      }
   },
   watch: {
      source(newVal, oldVal) {
         if (newVal && newVal !== oldVal) {
            this.popupStyle = { top: "0px", left: "0px" }
            this.oldSource = oldVal
            this.$nextTick(() => {
               this.positionPopup()
            })
         }
      }
   },
   computed: {
      ...mapState(useMainStore, ["popupPreview", "items"]),
      source() {
         return this.popupPreview?.url
      }
   },
   mounted() {
      window.addEventListener("mousemove", this.updateCursorPosition)
   },
   beforeUnmount() {
      window.removeEventListener("mousemove", this.updateCursorPosition)
   },
   methods: {
      ...mapActions(useMainStore, ["clearPopupPreview"]),

      updateCursorPosition(event) {
         let foundItem = this.items.find(item => item.id === this.popupPreview?.file_id)
         if (!foundItem) {
            this.clearPopupPreview()
            return
         }

         this.cursorX = event.clientX
         this.cursorY = event.clientY
         this.calculatePopupStyle()
      },
      positionPopup() {
         if (!this.source) return
         const popup = this.$refs.popup
         if (!popup) return

         const img = new Image()
         img.src = this.source

         img.onload = () => {
            this.width = img.naturalWidth
            this.height = img.naturalHeight
            this.calculatePopupStyle()
         }
      },
      calculatePopupStyle() {
         const { innerWidth, innerHeight } = window
         const padding = 50

         let imageWidth = this.width
         let imageHeight = this.height

         // Determine scaling
         const maxDim = Math.max(imageWidth, imageHeight)

         if (maxDim < 700) {
            const scale = 700 / maxDim
            imageWidth *= scale
            imageHeight *= scale
         } else if (maxDim > 700) {
            const scale = 700 / maxDim
            imageWidth *= scale
            imageHeight *= scale
         }

         // Keep within viewport (optional)
         imageWidth = Math.min(imageWidth, innerWidth - 2 * padding)
         imageHeight = Math.min(imageHeight, innerHeight - 2 * padding)

         // Position centered on cursor
         let left = this.cursorX - imageWidth / 2
         let top = this.cursorY - imageHeight / 2

         left = Math.max(padding, Math.min(left, innerWidth - imageWidth - padding))
         top = Math.max(padding, Math.min(top, innerHeight - imageHeight - padding))

         this.popupStyle = {
            top: `${top}px`,
            left: `${left}px`,
            width: `${imageWidth}px`,
            height: `${imageHeight}px`,
            minWidth: `${imageWidth}px`,
            minHeight: `${imageHeight}px`,
            maxWidth: `${Math.min(imageWidth, 600)}px`,
            maxHeight: `${Math.min(imageHeight, 600)}px`,
            transform: "none",
            zIndex: "100000"
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