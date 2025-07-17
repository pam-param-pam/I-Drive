<template>
   <div id="save-button" ref="saveButton" class="save-file">
      <div class="tooltip">{{ $t(message) }}</div>
      <svg
         v-if="currentState === 'normal'"
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
         <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
         <polyline points="17 21 17 13 7 13 7 21"></polyline>
         <polyline points="7 3 7 8 15 8"></polyline>
      </svg>
      <svg
         v-else-if="currentState === 'loading'"
         class="loading-icon"
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
         <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
         <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="1"></path>
      </svg>
      <svg
         v-else-if="currentState === 'success'"
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
         <path d="M9 16l-4-4 1.41-1.41L9 13.17l8.59-8.59L19 6z"></path>
      </svg>
   </div>
</template>

<script>
export default {
   name: 'SaveButton',

   data() {
      return {
         message: 'buttons.saveFile',
         currentState: 'normal'
      }
   },

   mounted() {
      this.observer = new MutationObserver((mutations) => {
         for (const m of mutations) {
            const newValue = m.target.getAttribute(m.attributeName)
            this.$nextTick(() => {
               this.onClassChange(newValue, m.oldValue)
            })
         }
      })

      let saveButtonElement = this.$refs.saveButton

      if (saveButtonElement) {
         this.observer.observe(saveButtonElement, {
            attributes: true,
            attributeOldValue: true,
            attributeFilter: ['class']
         })

         this.updateStateFromClass()
      } else {
         console.error('saveButton reference not found')
      }
   },

   beforeUnmount() {
      if (this.observer) {
         this.observer.disconnect()
      }
   },

   methods: {
      updateStateFromClass() {
         let button = this.$refs.saveButton
         let classList = button.classList

         if (classList.contains('loading')) {
            this.currentState = 'loading'
            this.message = 'buttons.savingFile'
         } else if (classList.contains('success')) {
            this.currentState = 'success'
            this.message = 'buttons.fileSaved'
         } else {
            this.currentState = 'normal'
            this.message = 'buttons.saveFile'
         }
      },

      onClassChange(newClass, oldClass) {
         this.updateStateFromClass()
      }
   }
}
</script>

<style scoped>
.code-editor .save-file {
   transition: 0.2s opacity ease;
   position: relative;
   opacity: 0.5;
   width: 24px;
   height: 24px;
   cursor: pointer;
}

.code-editor .save-file:focus {
   outline: none;
}

.code-editor .save-file > svg {
   pointer-events: none;
}

.code-editor .save-file.normal {
   opacity: 0.5;
}

.code-editor .save-file.loading {
   opacity: 0.5;
}

.code-editor .save-file.success {
   opacity: 0.5;
}

.code-editor .save-file:hover {
   opacity: 1;
}

.code-editor .save-file:hover > .tooltip {
   display: block;
}

.code-editor .save-file > .tooltip {
   font-family: sans-serif;
   display: none;
   position: absolute;
   bottom: -50px;
   left: -96px;
   font-size: 12px;
   color: white;
   background: rgba(0, 0, 0, 0.8);
   box-sizing: border-box;
   text-align: center;
   border-radius: 4px;
   padding: 8px 12px;
   white-space: nowrap;
   z-index: 10;
}

/* Loading Spinner Animation */
@keyframes spin {
   0% {
      transform: rotate(0deg);
   }
   100% {
      transform: rotate(360deg);
   }
}

.loading-icon {
   animation: spin 1s linear infinite;
}

.code-editor .save-file.success {
   width: 32px;
   height: 32px;

   top: 12px !important;
   right: 55px !important;
}

.code-editor .save-file.success svg path {
   stroke-width: 1;
}
</style>
