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

   emits: ['hide'],

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

   watch: {
      show(val) {
         if (val) {
            document.addEventListener('mouseup', this.hideContextMenu)
         } else {
            document.removeEventListener('mouseup', this.hideContextMenu)
         }
      }
   },

   beforeUnmount() {
      document.removeEventListener('mouseup', this.hideContextMenu)
   },

   methods: {
      hideContextMenu() {
         this.$emit('hide')
      }
   }
}
</script>
<style>
.context-menu {
   position: fixed;
   min-width: 200px;
   border: 1px solid rgba(0, 0, 0, 0.2);
   box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
   z-index: 1000;
   background-color: var(--surfacePrimary);
}

.context-menu .action {
   width: 100%;
   border-radius: 0;
   display: flex;
   align-items: center;
}
</style>
