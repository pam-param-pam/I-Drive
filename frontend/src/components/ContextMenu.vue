<template>
   <div
      v-show="show"
      ref="contextMenu"
      :style="{
         top: `${top}px`,
         left: `${left}px`
      }"
      class="context-menu"
   >
      <slot />
   </div>
</template>

<script>
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   props: {
      show: {
         type: Boolean,
         required: true
      },
      pos: {
         type: Object,
         required: true,
         default: () => ({ x: 0, y: 0 })
      }
   },

   data() {
      return {
         contextMenu: null
      }
   },

   computed: {
      top() {
         return Math.min(this.pos.y, window.innerHeight - (this.contextMenu?.clientHeight || 0))
      },
      left() {
         return Math.min(this.pos.x, window.innerWidth - (this.contextMenu?.clientWidth || 0))
      }
   },
   mounted() {
      document.addEventListener("mouseup", this.closeContextMenu)
   },

   beforeUnmount() {
      document.removeEventListener("mouseup", this.closeContextMenu)
   },

   methods: {
      ...mapActions(useMainStore, ["closeContextMenu"])
   }
}
</script>
<style>
.context-menu {
  position: fixed;
  min-width: 200px;
  border: 1px solid rgba(0, 0, 0, 0.2);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
  z-index: 100000;
  background-color: var(--surfacePrimary);
}

.context-menu .action {
  width: 100%;
  border-radius: 0;
  display: flex;
  align-items: center;
}
</style>
