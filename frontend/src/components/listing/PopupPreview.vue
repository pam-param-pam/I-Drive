<template>
  <div class="popup-preview" v-show="source" ref="popup" :style="popupStyle">
    <img :src="source" alt="Popup image" />
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
         cursorX: 0,
         cursorY: 0
      }
   },
   watch: {
      source(newVal) {
         if (newVal) {
            this.$nextTick(() => {
               this.positionPopup()
            })
         }
      }
   },
   computed: {
      ...mapState(useMainStore, ['popupPreviewURL']),
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
         let popup = this.$refs.popup
         if (!popup) return

         let { innerWidth, innerHeight } = window
         let width = popup.offsetWidth
         let height = popup.offsetHeight
         let padding = 10

         let minLeft = 320
         let minTop = padding + 100


         let left = this.cursorX - width / 2
         left = Math.max(minLeft, Math.min(left, innerWidth - width))

         // Prefer below or above cursor based on Y position
         let top
         let isBottomHalf = this.cursorY > innerHeight / 2

         if (isBottomHalf) {
            // Place above
            top = this.cursorY - height - padding
            top = Math.max(minTop, top)
         } else {
            // Place below
            top = this.cursorY + padding
            if (top + height > innerHeight) {
               top = innerHeight - height
               top = Math.max(minTop, top) // Enforce minTop again
            }
         }

         this.popupStyle = {
            top: `${top}px`,
            left: `${left}px`,
            "max-width": "800px",
            transform: "none"
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
}
</style>