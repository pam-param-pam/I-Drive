<template>
   <div class="close-button">
      <div class="tooltip">{{ message }}</div>
      <svg
         fill="none"
         height="100%"
         stroke="currentColor"
         stroke-linecap="round"
         stroke-linejoin="round"
         stroke-width="3"
         viewBox="0 0 24 24"
         width="100%"
         xmlns="http://www.w3.org/2000/svg"
      >
         <line x1="18" x2="6" y1="6" y2="18"></line>
         <line x1="6" x2="18" y1="6" y2="18"></line>
      </svg>
   </div>
</template>

<script>
export default {
   name: 'CloseButton',

   data() {
      return {
         message: 'Close'
      }
   }
}
</script>

<style scoped>
.close-button {
   transition: 0.2s opacity ease;
   position: relative;
   opacity: 0.5;
   width: 32px;
   height: 32px;
   cursor: pointer;
}

.close-button:focus {
   outline: none;
}

.close-button > svg {
   pointer-events: none;
}

.close-button:hover {
   opacity: 1;
   color: #ee4c4c;
}

.close-button:hover > .tooltip {
   display: block;
}

.close-button > .tooltip {
   font-family: sans-serif;
   display: none;
   position: absolute;
   bottom: -10px;
   left: 40px;
   font-size: 12px;
   color: white;
   width: 84px;
   height: 30px;
   line-height: 30px;
   background: rgba(0, 0, 0, 0.8);
   box-sizing: border-box;
   text-align: center;
   border-radius: 4px;
}
</style>
