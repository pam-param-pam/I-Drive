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
<style>
.message {
  text-align: center;
  font-size: 2em;
  margin: 1em auto;
  display: block !important;
  width: 95%;
  color: rgba(0, 0, 0, 0.3);
  font-weight: 500;
}

.message i {
  font-size: 2.5em;
  margin-bottom: .2em;
  display: block;
}
</style>
