<template>
   <div class="dashboard" @dragover.prevent @drop.prevent="onDrop">
      <header-bar>
         <title></title>
      </header-bar>

      <div id="nav">
         <div class="wrapper">
            <ul>
               <router-link :draggable="false" to="/settings/profile">
                  <li :class="{ active: $route.path === '/settings/profile' }" :draggable="false">
                     {{ $t("settings.profile") }}
                  </li>
               </router-link>

               <router-link v-if="perms.share" :draggable="false" to="/settings/shares">
                  <li :class="{ active: $route.path === '/settings/shares' }" :draggable="false">
                     {{ $t("settings.shareManagement") }}
                  </li>
               </router-link>

               <router-link :draggable="false" to="/settings/discord" data-tour="discord-settings">
                  <li :class="{ active: $route.path === '/settings/discord' }" :draggable="false">
                     {{ $t("settings.discordSettings") }}
                  </li>
               </router-link>
               <router-link :draggable="false" to="/settings/devices">
                  <li :class="{ active: $route.path === '/settings/devices' }" :draggable="false">
                     {{ $t("settings.devices") }}
                  </li>
               </router-link>
            </ul>
         </div>
      </div>

      <router-view></router-view>
   </div>
</template>

<script>
import HeaderBar from "@/components/header/HeaderBar.vue"
import { name } from "@/utils/constants.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"

export default {
   name: "settings",

   components: {
      HeaderBar
   },

   computed: {
      ...mapState(useMainStore, ["perms"])
   },

   methods: {
      ...mapActions(useMainStore, ["setDisabledCreation"]),

      onDrop(event) {
         const dt = event.dataTransfer

         if (!dt) return

         // Case 1: Files (most reliable)
         if (dt.files && dt.files.length > 0) {
            this.$toast.error(this.$t("toasts.uploadNotAllowedHere"))
            return
         }

         // Case 2: Items (needed for folder detection in Chromium)
         if (dt.items && dt.items.length > 0) {
            const hasFileLikeItem = Array.from(dt.items).some(
               item => item.kind === "file"
            )

            if (hasFileLikeItem) {
               this.$toast.error(this.$t("toasts.uploadNotAllowedHere"))
            }
         }
      }

   },

   mounted() {
      document.title = this.$t("settings.settingsName") + " - " + name
      document.body.classList.add("enable-scroll")
   },

   unmounted() {
      document.body.classList.remove("enable-scroll")
   },

   created() {
      this.setDisabledCreation(true)
   }

}
</script>
<style scoped>
.wrapper {
  overflow-x: scroll;
  -webkit-overflow-scrolling: touch;
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
