<template>
  <button @click="action" :aria-label="label" :title="label" class="action">

    <i class="material-icons">{{ icon }}</i>
    <span>{{ label }}</span>

    <span v-if="counter > 0" class="counter">{{ counter }}</span>
  </button>
</template>

<script>

import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "action",
   props: ["icon", "label", "counter", "show", "promptProps"],
   emits: ["action"],
   methods: {
      ...mapActions(useMainStore, ["showHover"]),
      action() {
         if (this.show) {
            if (this.promptProps) {
               this.showHover({
                  "prompt": this.show,
                  "props": this.promptProps
               })
            }
            else {
               this.showHover(this.show)

            }
         }
         this.$emit("action")
      }
   }
}
</script>

<style></style>
