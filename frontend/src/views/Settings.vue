<template>
  <div class="dashboard">
    <header-bar showMenu showLogo />



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
    <div v-else>
        <router-view></router-view>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";

import HeaderBar from "@/components/header/HeaderBar.vue";

export default {
  name: "settings",
  components: {
    HeaderBar,
  },
  computed: {
    ...mapState(["user", "loading", "perms"]),
  },
};
</script>
