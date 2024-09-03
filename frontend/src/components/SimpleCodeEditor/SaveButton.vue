<template>
  <div id="save-button" class="save-file" ref="saveButton">
    <div class="tooltip">{{ message }}</div>
    <svg
      v-if="currentState === 'normal'"
      xmlns="http://www.w3.org/2000/svg"
      width="100%"
      height="100%"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
      <polyline points="17 21 17 13 7 13 7 21"></polyline>
      <polyline points="7 3 7 8 15 8"></polyline>
    </svg>
    <svg
      v-else-if="currentState === 'loading'"
      class="loading-icon"
      xmlns="http://www.w3.org/2000/svg"
      width="100%"
      height="100%"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
      <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="1"></path>
    </svg>
    <svg
      v-else-if="currentState === 'success'"
      xmlns="http://www.w3.org/2000/svg"
      width="100%"
      height="100%"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M9 16l-4-4 1.41-1.41L9 13.17l8.59-8.59L19 6z"></path>
    </svg>
  </div>
</template>

<script>
export default {
   name: "SaveButton",
   data() {
      return {
         message: "Save File",
         currentState: 'normal', // Default state
      };
   },
   mounted() {
      // Create an observer to monitor class changes
      this.observer = new MutationObserver(mutations => {
         for (const m of mutations) {
            const newValue = m.target.getAttribute(m.attributeName);
            this.$nextTick(() => {
               this.onClassChange(newValue, m.oldValue);
            });
         }
      });

      // Ensure saveButton is correctly referenced
      const saveButtonElement = this.$refs.saveButton;

      // Verify that saveButtonElement is a valid DOM node
      if (saveButtonElement) {
         this.observer.observe(saveButtonElement, {
            attributes: true,
            attributeOldValue: true,
            attributeFilter: ['class'],
         });

         this.updateStateFromClass();
      } else {
         console.error('saveButton reference not found');
      }
   },
   beforeUnmount() {
      if (this.observer) {
         this.observer.disconnect();
      }
   },
   methods: {
      updateStateFromClass() {
         const button = this.$refs.saveButton;
         const classList = button.classList;

         if (classList.contains('loading')) {
            this.currentState = 'loading';
            this.message = "Saving...";
         } else if (classList.contains('success')) {
            this.currentState = 'success';
            this.message = "Saved!";
         } else {
            this.currentState = 'normal';
            this.message = "Save File";
         }
      },
      onClassChange(newClass, oldClass) {
         this.updateStateFromClass();
      }
   }
};
</script>

<style>
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
 fill: green; /* Optional: Change color to indicate success */
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
 width: 84px;
 height: 30px;
 line-height: 30px;
 background: rgba(0, 0, 0, 0.8);
 box-sizing: border-box;
 text-align: center;
 border-radius: 4px;
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
 stroke-width: 1; /* Reduce stroke width to make the icon less bold */
}
</style>
