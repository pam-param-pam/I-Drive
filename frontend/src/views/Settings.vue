<template>
  <div class="dashboard">
    <header-bar />

    <div id="nav">
      <div class="wrapper">
        <ul>
          <router-link to="/settings/profile">
            <li :class="{ active: $route.path === '/settings/profile' }">
              {{ $t("settings.profileSettings") }}
            </li>
          </router-link>
          <router-link to="/settings/shares" v-if="perms.share">
            <li :class="{ active: $route.path === '/settings/shares' }">
              {{ $t("settings.shareManagement") }}
            </li>
          </router-link>
          <router-link to="/settings/discord">
            <li :class="{ active: $route.path === '/settings/discord' }">
              {{ $t("settings.discordSettings") }}
            </li>
          </router-link>
        </ul>
      </div>
    </div>

    <div v-if="loading">
      <h2 class="message delayed">
        <div class="spinner">
          <div class="bounce1"></div>
          <div class="bounce2"></div>
          <div class="bounce3"></div>
        </div>
        <span>{{ $t("files.loading") }}</span>
      </h2>
    </div>

    <router-view></router-view>
  </div>
</template>

<script>
import HeaderBar from "@/components/header/HeaderBar.vue"
import { name } from "@/utils/constants.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"

export default {
   name: "settings",
   components: {
      HeaderBar
   },
   computed: {
      ...mapState(useMainStore, ["loading", "perms"])

   },
   methods: {
      ...mapActions(useMainStore, ["setDisabledCreation"])
   },
   mounted() {
      document.title = this.$t("settings.settingsName") + " - " + name
      document.body.classList.add("enable-scroll")
   },
   unmounted() {
      document.body.classList.remove("enable-scroll")
   },
   created() {
      this.setDisabledCreation(true)
   }

}
</script>
<style scoped>
.wrapper {
 overflow-x: scroll;
 -webkit-overflow-scrolling: touch;
 -ms-overflow-style: none;
 scrollbar-width: none;
}

</style>