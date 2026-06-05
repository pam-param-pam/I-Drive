<template>
   <div class="card floating notification-prompt">

      <div class="card-title">
         <h2>{{ displayTitle }}</h2>
      </div>

      <div class="card-content">

         <p class="notification-message">
            {{ displayMessage }}
         </p>

         <div v-if="details.length" class="notification-details">
            <div
              v-for="detail in details"
              :key="detail.label"
              class="notification-detail-row"
            >
               <span class="notification-detail-label">{{ detail.label }}</span>
               <span class="notification-detail-value">{{ detail.value }}</span>
            </div>
         </div>

         <p class="notification-time">
            {{ notification.time }}
         </p>

      </div>

      <div class="card-action">

         <button
           v-for="action in notificationActions"
           :key="action.label"
           class="button button--flat button--blue"
           @click="handleAction(action)"
         >
            {{ getActionLabel(action) }}
         </button>

         <button
           :aria-label="$t('buttons.markUnread')"
           :title="$t('buttons.markUnread')"
           class="button button--flat button--red"
           @click="markUnread()"
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
import { NotificationKind } from "@/utils/constants.js"

export default {
   name: "SingleNotification",

   props: {
      notification: { type: Object, required: true }
   },

   data() {
      return {
         markRead: true
      }
   },

   computed: {
      ...mapState(useMainStore, ["currentPrompt"]),

      notificationKind() {
         return this.notification.kind || NotificationKind.GENERAL
      },

      notificationData() {
         return this.notification.data || {}
      },

      notificationActions() {
         return this.notification.actions || []
      },

      displayTitle() {
         if (this.notificationKind === NotificationKind.NEW_DEVICE_LOGIN) {
            return this.$t("notifications.newDeviceLoginTitle")
         }

         return this.$t(this.notification.title)
      },

      displayMessage() {
         if (this.notificationKind === NotificationKind.NEW_DEVICE_LOGIN) {
            return this.$t("notifications.newDeviceLoginMessage")
         }

         return this.$t(this.notification.message)
      },

      details() {
         if (this.notificationKind === NotificationKind.NEW_DEVICE_LOGIN) {
            return [
               { label: this.$t("notifications.fields.device_id"), value: this.notificationData.device_id },
               { label: this.$t("notifications.fields.device"), value: this.notificationData.device_name },
               { label: this.$t("notifications.fields.ipAddress"), value: this.notificationData.ip_address },
               { label: this.$t("notifications.fields.device_type"), value: this.notificationData.device_type },
               { label: this.$t("notifications.fields.country"), value: this.notificationData.country },
               { label: this.$t("notifications.fields.city"), value: this.notificationData.city },

            ].filter(item => item.value)
         }
         return []
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      markUnread() {
         this.markRead = false
         this.cancel()
      },

      getActionLabel(action) {
         return action.label_key ? this.$t(action.label_key) : action.label
      },

      handleAction(action) {
         if (action.type === "route" && action.to) {
            this.$router.push(action.to)
            this.cancel()
            return
         }

         if (action.type === "external_url" && action.url) {
            window.open(action.url, "_blank", "noopener,noreferrer")
            this.cancel()
            return
         }

         console.warn("Unknown notification action", action)
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