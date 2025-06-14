<template>
   <div
      :class="{ disabled: disabled }"
      class="dropdown"
      tabindex="0"
      @click="toggleDropdown"
      @focusout="hideDropdown"
   >
      <div class="title">
         <div>{{ title }}</div>
         <svg
            v-if="!this.disabled"
            :style="{ transform: show ? 'rotateZ(180deg)' : 'rotateZ(0deg)' }"
            fill="none"
            height="16"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            viewBox="0 0 24 24"
            width="16"
            xmlns="http://www.w3.org/2000/svg"
         >
            <polyline points="6 9 12 15 18 9"></polyline>
         </svg>
      </div>
      <transition name="fade">
         <div v-if="show" :style="{ width: width, height: height }" class="list">
            <slot></slot>
         </div>
      </transition>
   </div>
</template>

<script>
export default {
   name: 'Dropdown',

   props: {
      width: {
         type: String,
         default: '80px'
      },
      height: {
         type: String,
         default: 'auto'
      },
      title: {
         type: String,
         default: ''
      },
      disabled: {
         type: Boolean,
         default: false
      },
      defaultDisplay: {
         type: Boolean,
         default: false
      }
   },

   data() {
      return {
         show: this.defaultDisplay
      }
   },

   methods: {
      toggleDropdown() {
         if (!this.disabled) {
            this.show = !this.show
         }
      },

      hideDropdown() {
         this.show = false
      }
   }
}
</script>

<style scoped>
.code-editor .dropdown .list.fade-enter-active,
.code-editor .dropdown .list.fade-leave-active {
   transition:
      transform 0.2s ease,
      opacity 0.2s ease;
}

.code-editor .dropdown .list.fade-enter-from,
.code-editor .dropdown .list.fade-leave-to {
   opacity: 0;
   transform: translateY(-10px);
}

.code-editor .dropdown {
   cursor: pointer;
   position: relative;
}

.code-editor .dropdown:focus {
   outline: none;
}

.code-editor .disabled {
   cursor: default;
}

.code-editor .disabled:hover > .title {
   opacity: 0.5 !important;
}

.code-editor .dropdown:hover > .title {
   opacity: 1;
}

.code-editor .dropdown > .title {
   transition: opacity 0.2s ease;
   opacity: 0.5;
   display: flex;
   align-items: center;
   -webkit-user-select: none;
   user-select: none;
}

.code-editor .dropdown > .title > div {
   white-space: nowrap;
   font-size: 14px;
   line-height: 16px;
}

.code-editor .dropdown > .title > svg {
   transition: 0.2s;
   margin-left: 3px;
   margin-top: 1px;
}

.code-editor .dropdown > .list {
   box-sizing: border-box;
   position: absolute;
   padding: 1px;
   border-radius: 6px;
   overflow: hidden;
   top: 24px;
   left: 0;
   box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.code-editor .dropdown > .list:before {
   content: '';
   position: absolute;
   top: 0px;
   left: 0px;
   z-index: -1;
   width: 100%;
   height: 100%;
   background: currentColor;
   opacity: 0.2;
}
</style>
