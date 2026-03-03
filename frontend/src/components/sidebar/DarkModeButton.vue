<template>
   <div>
      <button
         :aria-label="$t('sidebar.toggleDarkMode')"
         :class="settings.theme"
         :title="$t('sidebar.toggleDarkMode')"
         class="dark-mode-toggle hide-mobile-tap"
         @click="toggleDarkMode"
      >
         <span class="material-icons">{{
            settings.theme !== 'dark' ? 'dark_mode' : 'light_mode'
         }}</span>
      </button>
   </div>
</template>

<script>
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'
import { updateSettings } from '@/api/user.js'
import throttle from 'lodash.throttle'

export default {
   name: 'DarkModeButton',

   computed: {
      ...mapState(useMainStore, ['settings', 'isLogged'])
   },

   methods: {
      ...mapActions(useMainStore, ['setTheme']),

      throttledUpdateSettings: throttle(function (newTheme) {
         updateSettings({ theme: newTheme })
      }, 1000),

      toggleDarkMode() {
         const themes = { light: 'dark', dark: 'light' }
         let newTheme = themes[this.settings.theme]
         this.setTheme(newTheme)

         if (!this.isLogged) return
         this.throttledUpdateSettings(newTheme)
      }
   }
}
</script>
<style scoped>
.dark-mode-toggle {
   margin-left: 15px;
   display: flex;
   align-items: center;
   justify-content: center;
   padding: 10px 15px;
   border: none;
   border-radius: 50%;
   font-size: 24px;
   cursor: pointer;
   outline: none;
}

@media (hover: none) {
   .dark-mode-toggle:hover {
      background-color: transparent;
      color: inherit;
   }
}

.dark-mode-toggle:active {
   background-color: transparent;
   color: inherit;
}

.dark-mode-toggle .material-icons {
   font-size: 28px;
}

.dark-mode-toggle.light {
   background-color: var(--background);
}

.dark-mode-toggle.dark {
   background-color: var(--background);
   color: #ffffff;
}
</style>
