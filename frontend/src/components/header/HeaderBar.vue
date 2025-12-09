<template>
   <header>
      <img v-if="showLogo" :src="logoURL" />
      <action
        v-if="showMenu"
        class="menu-button hideMobileTap"
        icon="menu"
        :label="$t('buttons.toggleSidebar')"
        @action="openSidebar()"
      />
      <slot />

      <action
        v-if="this.deviceControlStatus.status === 'active_master' || this.deviceControlStatus.status === 'active_slave'"
        id="deviceControl"
        class="hide-mobile-tap"
        icon="cast"
        :label="$t('buttons.deviceControl')"
        @action="showHover('controlDevice')"
      />

      <div id="dropdown" :class="{ active: this.currentPromptName === 'more' }">
         <slot name="actions" />
      </div>

      <action
         v-if="this.$slots.actions"
         id="more"
         class="hide-mobile-tap"
         icon="more_vert"
         :label="$t('buttons.more')"
         @action="showHover('more')"
      />
      <div
         class="overlay"
         v-show="this.currentPromptName === 'more'"
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
      ...mapState(useMainStore, ["settings", "currentPromptName", "deviceControlStatus"])
   },
   methods: {
      ...mapActions(useMainStore, ["showHover", "closeHover"]),
      openSidebar() {
         this.showHover("sidebar")
      }
   }

}
</script>
