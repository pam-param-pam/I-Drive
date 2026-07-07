<template>
   <div class="card floating notification-prompt">

      <div class="card-title">
         <h2>{{ title }}</h2>
      </div>

      <div class="card-content">

         <p class="notification-message">
            {{ message }}
         </p>

         <div v-if="details.length" class="notification-details">
            <div
              v-for="detail in details"
              :key="detail.key"
              class="notification-detail-row"
            >
               <span class="notification-detail-label">
                  {{ $t(`notifications.fields.${detail.key}`) }}
               </span>

               <span class="notification-detail-value">
                  {{ detail.value }}
               </span>
            </div>
         </div>

         <p class="notification-time">
            {{ notification.time }}
         </p>

      </div>

      <div class="card-action">
         <button
           :aria-label="$t('buttons.markUnread')"
           :title="$t('buttons.markUnread')"
           class="button button--flat button--red"
           @click="markUnread"
         >
            {{ $t("buttons.markUnread") }}
         </button>

         <button
           :aria-label="$t('buttons.close')"
           :title="$t('buttons.close')"
           class="button button--flat button--grey"
           @click="cancel"
         >
            {{ $t("buttons.close") }}
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
      notification: { type: Object, required: true },
      title: { type: String, required: true },
      message: { type: String, required: true }
   },

   data() {
      return {
         markRead: true,
         hiddenDetailKeys: ["created_at", "expires_at", "user_agent"]
      }
   },

   computed: {
      ...mapState(useMainStore, ["currentPrompt"]),

      details() {
         const hiddenKeys = new Set(this.hiddenDetailKeys)

         return Object.entries(this.notification.data || {})
           .filter(([key, value]) =>
             !hiddenKeys.has(key) &&
             value !== null &&
             value !== undefined &&
             value !== ""
           )
           .map(([key, value]) => ({ key, value }))
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      markUnread() {
         this.markRead = false
         this.cancel()
      },

      cancel() {
         if (this.currentPrompt.confirm) {
            this.currentPrompt.confirm(this.markRead)
         }

         this.closeHover()
      }
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

.notification-details {
   margin-top: 14px;
   padding: 10px;
   border-radius: 6px;
   background: rgba(0, 0, 0, 0.04);
}

.notification-detail-row {
   display: flex;
   justify-content: space-between;
   gap: 12px;
   margin-bottom: 6px;
   font-size: 13px;
}

.notification-detail-row:last-child {
   margin-bottom: 0;
}

.notification-detail-label {
   opacity: 0.65;
}

.notification-detail-value {
   text-align: right;
   word-break: break-word;
}
</style>