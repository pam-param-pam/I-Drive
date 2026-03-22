<template>
   <div class="card floating notifications-card">
      <div class="card-title">
         <h2>{{ $t("prompts.notifications") }}</h2>
      </div>

      <div
        ref="notificationsContainer"
        class="card-content notifications-content"
      >
         <div v-if="!notifications.length && !loadingMore" class="notif-empty">
            {{ $t("prompts.noNotifications") }}
         </div>

         <div
           v-for="n in notifications"
           :key="n.id"
           :class="[`type-${n.type}`, { unread: !n.is_read }]"
           class="notif-item"
           @click="openNotification(n)"
         >
            <div class="notif-header-row">
               <div class="notif-title">{{ n.title }}</div>
               <span v-if="!n.is_read" class="notif-dot"></span>
            </div>

            <div class="notif-message">{{ n.message }}</div>
            <div class="notif-time">{{ n.time }}</div>
         </div>

         <div
           v-if="loadingMore"
           class="notif-skeleton-wrapper"
         >
            <div v-for="i in 4" :key="'skeleton-'+i" class="notif-skeleton">
               <div class="skeleton-line skeleton-title"></div>
               <div class="skeleton-line skeleton-text"></div>
               <div class="skeleton-line skeleton-time"></div>
            </div>
         </div>
      </div>

      <div class="card-action notifications-actions">
         <button
           v-if="!showAll"
           :disabled="loadingMore"
           class="button button--flat"
           @click="loadMore"
         >
            {{ loadingMore
           ? $t("prompts.loading")
           : $t("prompts.showPrevious") }}
         </button>

         <button
           :disabled="loadingMore || !unread.length"
           class="button button--flat button--red"
           @click="markAllRead()"
         >
            {{ $t("buttons.markAllRead") }}
         </button>

         <button
           class="button button--flat button--grey"
           @click="closeHover()"
         >
            {{ $t("buttons.close") }}
         </button>
      </div>
   </div>
</template>

<script>
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { getNotifications, setNotificationsStatus } from "@/api/user.js"

export default {
   name: "notifications",

   data() {
      return {
         loadingMore: false,
         notifications: [],
         showAll: false
      }
   },

   computed: {
      ...mapState(useMainStore, ["user"]),

      unread() {
         return this.notifications.filter(n => !n.is_read)
      }
   },

   created() {
      this.fetchNotifications(false)
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "showHover", "setUnreadNotifications"]),

      async fetchNotifications(more) {
         try {
            this.loadingMore = true

            this.notifications = await getNotifications(more)
            this.showAll = more
         } finally {
            this.loadingMore = false
         }
      },

      async loadMore() {
         if (this.loadingMore) return
         await this.fetchNotifications(true)
      },

      openNotification(notification) {
         this.showHover({
            prompt: "SingleNotification",
            props: { notification },
            confirm: (value) => {
               if (value) {
                  if (!notification.is_read) {
                     this.markAsRead([notification])
                  }
               } else {
                  if (notification.is_read) {
                     this.markAsUnread([notification])
                  }
               }
            }
         })
      },

      async markAllRead() {
         await this.setReadState(this.unread, true)
      },

      async markAsRead(list) {
         await this.setReadState(list, true)
      },

      async markAsUnread(list) {
         await this.setReadState(list, false)
      },

      async setReadState(list, isRead) {
         const ids = list.map(n => n.id)
         if (!ids.length) return

         await setNotificationsStatus({ ids, is_read: isRead })

         list.forEach(n => n.is_read = isRead)

         const delta = isRead ? -ids.length : ids.length
         this.setUnreadNotifications(this.user.unreadNotifications + delta)
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

.notif-item.unread {
   background: rgba(100, 181, 246, 0.06);
}

.notif-dot {
   width: 8px;
   height: 8px;
   background: #64b5f6;
   border-radius: 50%;
   margin-right: 10px;
}

.type-error { border-left: 3px solid #e57373; }
.type-success { border-left: 3px solid #66bb6a; }
.type-info { border-left: 3px solid #64b5f6; }

.notifications-actions {
   justify-content: space-between;
}
</style>