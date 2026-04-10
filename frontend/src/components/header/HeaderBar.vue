<template>
   <header>
      <img v-if="showLogo" :src="logoURL" />
      <action
         v-if="showMenu"
         :label="$t('buttons.toggleSidebar')"
         class="menu-button hideMobileTap"
         icon="menu"
         @action="openSidebar()"
      />
      <slot />

      <action
         v-if="this.multiSelection"
         :label="$t('buttons.multiSelect')"
         :outside="true"
         icon="close"
         @action="this.setMultiSelection(false)"
      />

      <div id="dropdown" :class="{ active: this.currentPromptName === 'more' }">
         <slot name="actions" />
      </div>

      <action
         v-if="this.$slots.actions"
         id="more"
         :label="$t('buttons.more')"
         class="hide-mobile-tap"
         icon="more_vert"
         @action="showHover('more')"
      />
      <div
         v-show="this.currentPromptName === 'more'"
         class="overlay"
         @click="closeHover()"
      />
   </header>
</template>

<script>
import { logoURL } from "@/utils/constants"

import Action from "@/components/header/Action.vue"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"

export default {
   name: "header-bar",

   components: { Action },
   emits: ["switchView"],

   props: {
      showLogo: {
         type: Boolean,
         default: () => true
      },
      showMenu: {
         type: Boolean,
         default: () => true
      }
   },

   data() {
      return {
         logoURL
      }
   },
   computed: {
      ...mapState(useMainStore, ["settings", "currentPromptName", "multiSelection"])
   },
   methods: {
      ...mapActions(useMainStore, ["showHover", "closeHover", "setMultiSelection"]),
      openSidebar() {
         this.showHover("sidebar")
      }
   }

}
</script>
