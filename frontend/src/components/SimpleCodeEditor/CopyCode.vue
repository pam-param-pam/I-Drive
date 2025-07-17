<template>
   <div class="copy-code" @click="showMessage" @mouseout="resetMessage">
      <div class="tooltip">{{ $t(message) }}</div>
      <svg
         fill="none"
         height="100%"
         stroke="currentColor"
         stroke-linecap="round"
         stroke-linejoin="round"
         stroke-width="2"
         viewBox="0 0 24 24"
         width="100%"
         xmlns="http://www.w3.org/2000/svg"
      >
         <rect height="13" rx="2" ry="2" width="13" x="9" y="9"></rect>
         <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
   </div>
</template>

<script>
export default {
   name: 'CopyCode',

   data() {
      return {
         message: 'buttons.copyText'
      }
   },

   methods: {
      showMessage() {
         this.message = 'buttons.copied'
      },

      resetMessage() {
         this.message = 'buttons.copyText'
      }
   }
}
</script>

<style scoped>
.code-editor .copy-code {
   transition: 0.2s opacity ease;
   position: relative;
   opacity: 0.5;
   width: 24px;
   height: 24px;
   cursor: pointer;
}

.code-editor .copy-code:focus {
   outline: none;
}

.code-editor .copy-code > svg {
   pointer-events: none;
}

.code-editor .copy-code:hover {
   opacity: 1;
}

.code-editor .copy-code:hover > .tooltip {
   display: block;
}

.code-editor .copy-code > .tooltip {
   font-family: sans-serif;
   display: none;
   position: absolute;
   bottom: -50px;
   left: -96px;
   font-size: 12px;
   color: white;
   background: rgba(0, 0, 0, 0.8);
   padding: 8px 12px;
   box-sizing: border-box;
   text-align: center;
   border-radius: 4px;
   white-space: nowrap;
   z-index: 10;
}
</style>
