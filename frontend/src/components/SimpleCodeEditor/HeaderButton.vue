<template>
   <div :style="style" class="header-button" @click="handleClick" @mouseout="resetMessage">
      <div class="tooltip">{{ message }}</div>
      <svg
         :viewBox="viewBox"
         fill="none"
         height="100%"
         stroke="currentColor"
         stroke-linecap="round"
         stroke-linejoin="round"
         stroke-width="2"
         width="100%"
         xmlns="http://www.w3.org/2000/svg"
      >
         <slot></slot>
      </svg>
   </div>
</template>

<script>
export default {
   name: 'HeaderButton',

   props: {
      initialMessage: {
         type: String,
         required: true
      },
      actionMessage: {
         type: String,
         required: true
      },
      viewBox: {
         type: String,
         default: '0 0 24 24'
      }
   },

   data() {
      return {
         message: this.initialMessage
      }
   },

   methods: {
      handleClick() {
         this.message = this.actionMessage
         this.$emit('action')
      },

      resetMessage() {
         this.message = this.initialMessage
      }
   }
}
</script>

<style scoped>
.header-button {
   transition: 0.2s opacity ease;
   position: relative;
   opacity: 0.5;
   width: 24px;
   height: 24px;
   cursor: pointer;
}

.header-button:focus {
   outline: none;
}

.header-button > svg {
   pointer-events: none;
}

.header-button:hover {
   opacity: 1;
}

.header-button:hover > .tooltip {
   display: block;
}

.header-button > .tooltip {
   font-family: sans-serif;
   display: none;
   position: absolute;
   font-size: 12px;
   color: white;
   width: 84px;
   height: 30px;
   line-height: 30px;
   background: rgba(0, 0, 0, 0.8);
   box-sizing: border-box;
   text-align: center;
   border-radius: 4px;
   white-space: nowrap; /* Prevent text wrapping */
}
</style>
