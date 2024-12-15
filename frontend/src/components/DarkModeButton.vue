<template>
  <div>
    <button
      @click="toggleDarkMode"
      :class="settings.theme"
      class="dark-mode-toggle"
      :aria-label="$t('sidebar.toggleDarkMode')"
      :title="$t('sidebar.toggleDarkMode')"
    >
      <span class="material-icons">{{ settings.theme==="dark" ? 'dark_mode' : 'light_mode' }}</span>
    </button>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { updateSettings } from "@/api/user.js"

export default {
   name: "DarkModeButton",

   computed: {
      ...mapState(useMainStore, ["settings"]),

   },
   methods: {
      ...mapActions(useMainStore, ["setTheme"]),

      toggleDarkMode() {
         const themes = {"light": "dark", "dark": "light"}
         let newTheme = themes[this.settings.theme]
         this.setTheme(newTheme)
         updateSettings({ "theme": newTheme })

      },

   },
};
</script>

<style scoped>
/* General Styles */
.dark-mode-toggle {
 display: flex;
 align-items: center;
 justify-content: center;
 padding: 10px 15px;
 margin-left: 0.5em;
 border: none;
 border-radius: 50%;
 font-size: 24px;
 cursor: pointer;
 transition: background-color 0.3s ease, color 0.3s ease;
 outline: none;
}

.dark-mode-toggle .material-icons {
 font-size: 28px;
}

/* Light Mode */
.dark-mode-toggle.light {
 background-color: var(--background);
}

/* Dark Mode */
.dark-mode-toggle.dark {
 background-color: var(--background);
 color: #ffffff;
}


</style>