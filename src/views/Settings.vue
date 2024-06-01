<template>
  <div class="dashboard">
    <header-bar showMenu showLogo />

    <div id="nav">
      <div class="wrapper">
        <ul>
          <router-link to="/settings/profile"
          ><li :class="{ active: $route.path === '/settings/profile' }">
            {{ $t("settings.profileSettings") }}
          </li></router-link
          >
          <router-link to="/settings/shares" v-if="perms.share"
          ><li :class="{ active: $route.path === '/settings/shares' }">
            {{ $t("settings.shareManagement") }}
          </li></router-link
          >
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
import {mapMutations, mapState} from "vuex"

import HeaderBar from "@/components/header/HeaderBar.vue"

export default {
  name: "settings",
  components: {
    HeaderBar,
  },
  computed: {
    ...mapState(["user", "loading", "perms"]),
  },
  methods: {
    ...mapMutations(["setDisableCreation"])
  },
  mounted() {
    document.title = "Settings - File Browser"

  },
  created() {
    this.setDisableCreation(true)
  },

}
</script>
