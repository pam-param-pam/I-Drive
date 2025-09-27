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
         const padding = 25

         const img = new Image()
         img.src = this.source

         img.onload = () => {
            const aspectRatio = img.naturalWidth / img.naturalHeight

            const maxWidth = Math.min(700, innerWidth - 2 * padding)
            const maxHeight = Math.min(700, innerHeight - 2 * padding)

            let width = maxWidth
            let height = width / aspectRatio

            if (height > maxHeight) {
               height = maxHeight
               width = height * aspectRatio
            }

            const minLeft = padding
            const minTop = padding

            let left = this.cursorX - width / 2
            left = Math.max(minLeft, Math.min(left, innerWidth - width - padding))

            let top
            const isBottomHalf = this.cursorY > innerHeight / 2

            if (isBottomHalf) {
               top = this.cursorY - height - padding
               top = Math.max(minTop, top)
            } else {
               top = this.cursorY + padding
               if (top + height > innerHeight - padding) {
                  top = innerHeight - height - padding
                  top = Math.max(minTop, top)
               }
            }

            this.popupStyle = {
               top: `${top}px`,
               left: `${left}px`,
               width: `${width}px`,
               height: `${height}px`,
               maxWidth: `${maxWidth}px`,
               maxHeight: `${maxHeight}px`,
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
}
</style>