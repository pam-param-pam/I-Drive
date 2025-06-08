<template>
  <header>
    <img v-if="showLogo" :src="logoURL"/>
    <action
      v-if="showMenu"
      class="menu-button hideMobileTap"
      icon="menu"
      :label="$t('buttons.toggleSidebar')"
      @action="openSidebar()"

    />

    <slot/>

    <div id="dropdown" :class="{ active: this.currentPromptName === 'more' }">
      <slot name="actions"/>
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
import {logoURL} from "@/utils/constants"

import Action from "@/components/header/Action.vue"
import {updateSettings} from "@/api/user.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"

export default {
   name: "header-bar",

   components: {Action},
   emits: ['switchView'],

   props: {
      showLogo: {
         type: Boolean,
         default: () => true,
      },
      showMenu: {
         type: Boolean,
         default: () => true,
      },
   },

   data() {
      return {
         logoURL,
         isDark: true
      }
   },
   computed: {
      ...mapState(useMainStore, ["settings", "currentPromptName"]),
   },
   methods: {
      ...mapActions(useMainStore, ["showHover", "closeHover"]),
      openSidebar() {
         this.showHover("sidebar")
      },
   },

}
</script>
