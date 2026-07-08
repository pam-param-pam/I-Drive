<template>
   <div class="card floating notifications-card">
      <div class="card-title">
         <h2>{{ $t("prompts.notifications") }}</h2>
      </div>

      <div
         ref="notificationsContainer"
         class="card-content notifications-content"
      >
         <div v-if="!notifications.length && !isLoading" class="notif-empty">
            <i class="material-icons notif-empty-icon">notifications_none</i>

            <div class="notif-empty-title">
               {{ $t("prompts.noNotifications") }}
            </div>

            <div class="notif-empty-subtitle">
               {{ $t("prompts.notificationsWillAppearHere") }}
            </div>
         </div>

         <div
            v-for="notification in notifications"
            :key="notification.id"
            :class="[`type-${notification.type}`, { unread: !notification.is_read }]"
            class="notif-item"
            @click="openNotification(notification)"
         >
            <div class="notif-header-row">
               <div class="notif-title">
                  {{ getNotificationTitle(notification) }}
               </div>

               <span v-if="!notification.is_read" class="notif-dot"></span>
            </div>

            <div class="notif-message">
               {{ getNotificationMessage(notification) }}
            </div>

            <div class="notif-time">
               {{ humanTime(notification.created_at) }}
            </div>
         </div>

         <div v-if="isLoading" class="notif-skeleton-wrapper">
            <div v-for="i in 5" :key="'skeleton-' + i" class="notif-skeleton">
               <div class="skeleton-line skeleton-title"></div>
               <div class="skeleton-line skeleton-text"></div>
               <div class="skeleton-line skeleton-time"></div>
            </div>
         </div>
      </div>

      <div class="card-action notifications-actions">
         <button
            v-if="canLoadMore"
            :disabled="isLoading"
            class="button button--flat"
            @click="loadMore"
         >
            {{ isLoading ? $t("prompts.loading") : $t("prompts.showPrevious") }}
         </button>

         <button
            :disabled="isLoading || !unread.length"
            class="button button--flat button--red"
            @click="markAllRead"
         >
            {{ $t("buttons.markAllRead") }}
         </button>

         <button
            class="button button--flat button--grey"
            @click="closeHover"
         >
            {{ $t("buttons.close") }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"

import { getNotifications, setNotificationsStatus } from "@/api/user.js"
import { useMainStore } from "@/stores/mainStore.js"
import { humanTime } from "@/utils/common.js"

export default {
   name: "Notifications",

   data() {
      return {
         initialLoading: false,
         loadingMore: false,
         notifications: [],
         page: 1,
         hasNext: false,
         unreadOnly: true
      }
   },

   computed: {
      ...mapState(useMainStore, ["user"]),

      unread() {
         return this.notifications.filter(notification => !notification.is_read)
      },

      canLoadMore() {
         return this.unreadOnly || this.hasNext
      },

      isLoading() {
         return this.initialLoading || this.loadingMore
      }
   },

   created() {
      this.fetchNotifications({ page: 1, replace: true, initial: true })
   },

   methods: {
      humanTime,
      ...mapActions(useMainStore, ["closeHover", "showHover", "setUnreadNotifications"]),

      getNotificationTitle(notification) {
         return this.$t(
            notification.title || `notifications.${notification.kind}.title`,
            notification.data || {}
         )
      },

      getNotificationMessage(notification) {
         return this.$t(notification.message || `notifications.${notification.kind}.message`, notification.data || {})
      },

      scrollToBottom() {
         const container = this.$refs.notificationsContainer

         if (container) {
            container.scrollTop = container.scrollHeight
         }
      },

      async fetchNotifications({ page, replace = false, initial = false, scrollToBottomOnLoad = false }) {
         if (this.isLoading) return

         try {
            if (initial) {
               this.initialLoading = true
            } else {
               this.loadingMore = true
            }

            if (scrollToBottomOnLoad) {
               await this.$nextTick()
               this.scrollToBottom()
            }

            const response = await getNotifications({ unreadOnly: this.unreadOnly, page })

            const items = response.items || []

            this.notifications = replace ? items : this.mergeNotifications(this.notifications, items)

            this.page = response.page
            this.hasNext = response.has_next
         } finally {
            this.initialLoading = false
            this.loadingMore = false
         }
      },

      mergeNotifications(current, incoming) {
         const existingIds = new Set(current.map(notification => notification.id))

         return [
            ...current,
            ...incoming.filter(notification => !existingIds.has(notification.id))
         ]
      },

      async loadMore() {
         if (this.isLoading) return

         if (this.unreadOnly && !this.hasNext) {
            this.unreadOnly = false
            this.page = 0
            this.hasNext = true
         }

         if (!this.hasNext) return

         await this.fetchNotifications({ page: this.page + 1, scrollToBottomOnLoad: true })
      },

      openNotification(notification) {
         this.showHover({
            prompt: "SingleNotification",
            props: {
               notification,
               title: this.getNotificationTitle(notification),
               message: this.getNotificationMessage(notification)
            },
            confirm: (markRead) => {
               if (markRead && !notification.is_read) {
                  this.markAsRead([notification])
               }

               if (!markRead && notification.is_read) {
                  this.markAsUnread([notification])
               }
            }
         })
      },

      async markAllRead() {
         await this.setReadState(this.unread, true)
      },

      async markAsRead(notifications) {
         await this.setReadState(notifications, true)
      },

      async markAsUnread(notifications) {
         await this.setReadState(notifications, false)
      },

      async setReadState(notifications, isRead) {
         const changed = notifications.filter(notification => notification.is_read !== isRead)
         const ids = changed.map(notification => notification.id)

         if (!ids.length) return

         await setNotificationsStatus({ ids, is_read: isRead })

         changed.forEach(notification => {
            notification.is_read = isRead
         })
      }
   }
}
</script>

<style>
.notifications-card {
  width: 480px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.notifications-content {
  overflow-y: auto;
  flex: 1;
  padding-right: 4px;
}

.notif-item {
  padding: 12px 0 12px 10px;
  border-bottom: 1px solid var(--divider, rgba(255, 255, 255, 0.08));
  position: relative;
  transition: background 0.15s ease;
  cursor: pointer;
}

.notif-item:hover {
  background: rgba(100, 181, 246, 0.08);
}

.notif-item.unread {
  background: rgba(100, 181, 246, 0.06);
}

.notif-item.unread:hover {
  background: rgba(100, 181, 246, 0.12);
}

.notif-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.notif-title {
  font-weight: 600;
  color: var(--textPrimary);
}

.notif-message {
  font-size: 13px;
  opacity: 0.8;
  margin-top: 3px;
  padding-right: 3em;
}

.notif-time {
  font-size: 12px;
  opacity: 0.5;
  margin-top: 6px;
}

.notif-dot {
  width: 8px;
  height: 8px;
  background: #64b5f6;
  border-radius: 50%;
  margin-right: 10px;
  flex: 0 0 auto;
}

.type-info {
  border-left: 3px solid #64b5f6;
}

.type-success {
  border-left: 3px solid #66bb6a;
}

.type-warning {
  border-left: 3px solid #ff8800;
}

.type-error {
  border-left: 3px solid rgba(155, 5, 5, 0.8);
}

.type-important {
  border-left: 3px solid #d31010;
}

.notifications-actions {
  justify-content: space-between;
}

.notif-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
  opacity: 0.8;
}

.notif-empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.notif-empty-title {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 6px;
}

.notif-empty-subtitle {
  font-size: 13px;
  opacity: 0.6;
}

.notif-skeleton-wrapper {
  padding: 8px 0;
}

.notif-skeleton {
  padding: 12px 0 12px 10px;
  border-bottom: 1px solid var(--divider, rgba(255, 255, 255, 0.08));
}

.skeleton-line {
  height: 10px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  animation: notif-skeleton-pulse 1.2s ease-in-out infinite;
}

.skeleton-title {
  width: 55%;
  margin-bottom: 8px;
}

.skeleton-text {
  width: 85%;
  margin-bottom: 8px;
}

.skeleton-time {
  width: 30%;
}

@keyframes notif-skeleton-pulse {
  0% {
    opacity: 0.45;
  }

  50% {
    opacity: 1;
  }

  100% {
    opacity: 0.45;
  }
}
</style>