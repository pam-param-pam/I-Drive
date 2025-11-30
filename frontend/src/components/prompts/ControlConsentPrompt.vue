<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t("prompts.controlRequest") }}</h2>
      </div>

      <div class="card-content">

         <!-- Device info preview -->
         <div class="device-info">
            <p><b>Device Name:</b> {{ masterDevice.device_name }}</p>
            <p><b>Device ID:</b> {{ masterDevice.device_id }}</p>
            <p><b>IP Address:</b> {{ masterDevice.ip_address }}</p>
            <p><b>User Agent:</b> {{ masterDevice.user_agent }}</p>
            <p v-if="masterDevice.country"><b>Country:</b> {{ masterDevice.country }}</p>
            <p v-if="masterDevice.city"><b>City:</b> {{ masterDevice.city }}</p>

            <p>
               <b>Device Type:</b> {{ "&#8205;" }}
               <i v-if="masterDevice.device_type === 'pc'" class="material-icons">desktop_windows</i>
               <i v-else-if="masterDevice.device_type === 'mobile'" class="material-icons">tablet</i>
               <i v-else-if="masterDevice.device_type === 'code'" class="material-icons">terminal</i>
               {{ masterDevice.device_type }}
            </p>
         </div>

      </div>

      <!-- Buttons -->
      <div class="card-action" v-if="mode === 'idle'">
         <button
            :aria-label="$t('buttons.reject')"
            :title="$t('buttons.reject')"
            class="button button--flat button--red"
            @click="rejectRequest"
         >
            {{ $t("buttons.reject") }}
         </button>

         <button
            :aria-label="$t('buttons.accept')"
            :title="$t('buttons.accept')"
            class="button button--flat button--primary"
            @click="approveRequest"
         >
            {{ $t("buttons.accept") }}
         </button>
      </div>

   </div>
</template>

<script>
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "ControlConsentPrompt",

   props: {
      masterDevice: {
         type: Object,
         required: true,
      }
   },

   data() {
      return {
         mode: "idle" // idle | approved | rejected
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      approveRequest() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": {"type": "approve"}}))
         this.closeHover()
      },

      rejectRequest() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": {"type": "reject"}}))
         this.closeHover()
      },
      close() {
         this.rejectRequest()
      }

   }
}
</script>

<style scoped>

.device-info {
   border: 1px solid #ccc;
   padding: 0.5rem;
   margin-top: 1rem;
   border-radius: 8px;
}

.device-info p {
   margin: 0.25rem 0;
}

.material-icons {
   font-size: 20px !important;
   vertical-align: -5px; /* moves it lower */
}
</style>
