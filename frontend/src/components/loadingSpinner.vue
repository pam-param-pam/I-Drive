<template>
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
</template>

<script>
import { mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "loadingSpinner",

   computed: {
      ...mapState(useMainStore, ["loading"]),
   },

}

</script>

