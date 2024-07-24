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
import { logoURL } from "@/utils/constants"

import Action from "@/components/header/Action.vue"
import {mapGetters, mapState} from "vuex"
import {updateSettings} from "@/api/user.js";

export default {
  name: "header-bar",
  props: ["showLogo", "showMenu"],
  components: {
    Action,
  },
  emits: ['switchView'],

  data() {
    return {
      logoURL,
      isDark: true
    }
  },
  computed: {
    ...mapState(["settings","perms", "isSearchActive"]),
    ...mapGetters(["currentPromptName", "selectedCount"]),
    viewIcon() {
      const icons = {
        list: "view_module",
        mosaic: "grid_view",
        "mosaic gallery": "view_list",
      }
      return icons[this.settings.viewMode]
    },
    isMobile() {
      return window.innerWidth <= 950
    },

  },
  methods: {
    openSidebar() {
      this.$store.commit("showHover", "sidebar")
    },
    async switchView() {

      const modes = {
        list: "mosaic",
        mosaic: "mosaic gallery",
        "mosaic gallery": "list",
      }
      console.log(this.settings.viewMode)
      const data = {
        viewMode: modes[this.settings.viewMode] || "list",
      }

      // Await ensures correct value for setItemWeight()
      await this.$store.commit("updateSettings", data)


      //this.setItemWeight()
      //this.fillWindow()


      await updateSettings(data)

    },

  },

}
</script>

<style></style>
