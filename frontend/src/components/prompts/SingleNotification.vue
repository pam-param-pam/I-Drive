<template>
   <div class="card floating notification-prompt">

      <div class="card-title">
         <h2>{{ notification.title }}</h2>
      </div>

      <div class="card-content">

         <p class="notification-message">
            {{ notification.message }}
         </p>

         <p class="notification-time">
            {{ notification.time }}
         </p>

      </div>

      <div class="card-action">
         <button
            :aria-label="$t('buttons.close')"
            :title="$t('buttons.close')"
            class="button button--flat button--grey"
            @click="closeHover()"
         >
            {{ $t('buttons.close') }}
         </button>
      </div>

   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "SingleNotification",
   props: {
      notification: { type: Object },
   },
   computed: {
      ...mapState(useMainStore, ["closeHover"])
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"])
   }
}
</script>

<style scoped>

.notification-prompt {
 width: 420px;
 max-width: 90vw;
}

.notification-message {
 margin-top: 6px;
 opacity: 0.9;
}

.notification-time {
 margin-top: 12px;
 font-size: 12px;
 opacity: 0.6;
}

</style>