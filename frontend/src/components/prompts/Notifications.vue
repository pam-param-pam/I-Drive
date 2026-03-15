<template>
   <div class="card floating notifications-card">
      <div class="card-title">
         <h2>{{ $t("prompts.notifications") }}</h2>
      </div>

      <div
         ref="notificationsContainer"
         class="card-content notifications-content"
      >
         <div v-if="!visibleNotifications.length && !loadingMore" class="notif-empty">
            {{ $t("prompts.noNotifications") }}
         </div>

         <div
            v-for="n in visibleNotifications"
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
            ref="skeletonBlock"
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
            v-if="hasOlder"
            :disabled="loadingMore"
            class="button button--flat"
            @click="loadMore"
         >
            {{ loadingMore
           ? $t("prompts.loading")
           : $t("prompts.showPrevious") }}
         </button>
         <button
            v-if="!hasOlder"
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
import { nextTick } from "vue"
import { getNotifications, setNotificationsStatus } from "@/api/user.js"

export default {
   name: "notifications",

   data() {
      return {
         loadingMore: false,
         visibleCount: 8,
         notifications: []
      }
   },

   computed: {
      ...mapState(useMainStore, ["user"]),
      visibleNotifications() {
         return this.notifications.slice(0, this.visibleCount)
      },
      hasOlder() {
         return this.visibleCount < this.notifications.length
      },
      unread() {
         return this.notifications.filter(n => !n.is_read)
      }
   },
   created() {
      this.fetchNotifications()
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover", "showHover", "setUnreadNotifications"]),
      async fetchNotifications() {
         try {
            this.loadingMore = true
            this.notifications = await getNotifications()
         } finally {
            this.loadingMore = false
         }
      },
      async loadMore() {
         if (!this.hasOlder || this.loadingMore) return

         this.loadingMore = true
         await nextTick()

         // scroll to skeleton
         const container = this.$refs.notificationsContainer
         const skeleton = this.$refs.skeletonBlock

         if (container && skeleton) {
            container.scrollTo({
               top: skeleton.offsetTop - 20,
               behavior: "smooth"
            })
         }

         await new Promise(resolve => setTimeout(resolve, 2000))

         this.visibleCount += 10
         this.loadingMore = false
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

/* type accent */
.type-error {
  border-left: 3px solid #e57373;
}

.type-success {
  border-left: 3px solid #66bb6a;
}

.type-info {
  border-left: 3px solid #64b5f6;
}

.notifications-actions {
  justify-content: space-between;
}

.notif-skeleton-wrapper {
  padding: 10px 0;
}

.notif-skeleton {
  padding: 12px 0;
  border-bottom: 1px solid var(--divider, rgba(255, 255, 255, 0.08));
}

.dark-mode .skeleton-line {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.10) 25%,
    rgba(255, 255, 255, 0.22) 37%,
    rgba(255, 255, 255, 0.10) 63%
  );
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
  border-radius: 4px;
  margin-bottom: 6px;
}

.skeleton-line {
  background: linear-gradient(
    90deg,
    rgba(0, 0, 0, 0.10) 25%,
    rgba(0, 0, 0, 0.22) 37%,
    rgba(0, 0, 0, 0.10) 63%
  );
  background-size: 400% 100%;
  animation: shimmer 1.2s ease infinite;
  border-radius: 4px;
  margin-bottom: 6px;
}

.skeleton-title {
  width: 60%;
  height: 14px;
}

.skeleton-text {
  width: 85%;
  height: 12px;
}

.skeleton-time {
  width: 30%;
  height: 10px;
}

@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>