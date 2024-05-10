<template>
  <header>
    <img v-if="showLogo !== undefined" :src="logoURL" />
    <action
      v-if="showMenu !== undefined"
      class="menu-button"
      icon="menu"
      :label="$t('buttons.toggleSidebar')"
      @action="openSidebar()"
    />

    <slot />

    <button @click="toggleDark()">
      <span class="ml-2">{{ isDark ? 'Dark' : 'Light' }}</span>
    </button>

    <div id="dropdown" :class="{ active: this.currentPromptName === 'more' }">
      <slot name="actions" />
    </div>

    <action
      v-if="this.$slots.actions"
      id="more"
      icon="more_vert"
      :label="$t('buttons.more')"
      @action="$store.commit('showHover', 'more')"
    />

    <div
      class="overlay"
      v-show="this.currentPromptName === 'more'"
      @click="$store.commit('closeHover')"
    />
  </header>
</template>

<script>
import { logoURL } from "@/utils/constants";

import Action from "@/components/header/Action.vue";
import { mapGetters } from "vuex";
import {useDark, useToggle} from '@vueuse/core'

export default {
  name: "header-bar",
  props: ["showLogo", "showMenu"],
  components: {
    Action,
    useDark,
  },
  data: function () {
    return {
      logoURL,
      isDark: true
    };
  },
  methods: {
    openSidebar() {
      this.$store.commit("showHover", "sidebar");
    },
    toggleDark() {
      useToggle(false)
    },

  },
  computed: {
    ...mapGetters(["currentPromptName"]),
  },
};
</script>

<style></style>
