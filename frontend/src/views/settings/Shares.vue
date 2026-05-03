<template>
   <loading-spinner v-if="loading" :loading="loading"/>
   <errors v-else-if="error" :error="error" />
   <div v-else class="row">
      <div class="column">
         <div class="card">
            <div class="card-title">
               <h2>{{ $t("settings.shareManagement") }}</h2>
            </div>

            <div v-if="shares.length > 0" class="card-content full">
               <table>
                  <tr>
                     <th>{{ $t("settings.name") }}</th>
                     <th class="expiry-column">{{ $t("settings.shareExpiry") }}</th>
                     <th></th>
                     <th></th>
                     <th></th>
                  </tr>

                  <tr v-for="share in shares" :key="share.token">
                     <td class="share-name-column">
                        <a :href="buildLink(share)" target="_blank">{{ share.name }}</a>
                     </td>
                     <td class="expiry-column">
                        <template v-if="share.expire !== 0"
                        >{{ humanTime(share.expire) }}
                        </template>
                        <template v-else>{{ $t("permanent") }}</template>
                     </td>
                     <td class="small">
                        <button
                           :aria-label="$t('buttons.info')"
                           :title="$t('buttons.info')"
                           class="action"
                           @click="showInfo($event, share)"
                        >
                           <i class="material-icons">info</i>
                        </button>
                     </td>
                     <td class="small">
                        <button
                           :aria-label="$t('buttons.delete')"
                           :title="$t('buttons.delete')"
                           class="action"
                           @click="deleteLink($event, share)"
                        >
                           <i class="material-icons">delete</i>
                        </button>
                     </td>
                     <td class="small">
                        <button
                           :aria-label="$t('buttons.copyToClipboard')"
                           :data-clipboard-text="buildLink(share)"
                           :title="$t('buttons.copyToClipboard')"
                           class="action copy-clipboard"
                        >
                           <i class="material-icons">content_paste</i>
                        </button>
                     </td>
                  </tr>
               </table>
            </div>
            <div v-else class="empty-state">
               <div class="empty-icon">
                  <i class="material-icons">share</i>
               </div>

               <h3 class="empty-title">
                  {{ $t('settings.noSharesTitle') }}
               </h3>

               <p class="empty-desc">
                  {{ $t('settings.noSharesDesc') }}
               </p>
            </div>
         </div>
      </div>
   </div>
</template>

<script>
import Clipboard from "clipboard"
import { getAllShares, deleteShare, getShareVisits } from "@/api/share.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import Errors from "@/components/Errors.vue"
import { humanTime } from "@/utils/common.js"
import loadingSpinner from "@/components/loadingSpinner.vue"

export default {
   name: "shares",

   components: {
      loadingSpinner,
      Errors
   },

   computed: {
      ...mapState(useMainStore, ["settings", "loading"])
   },

   data() {
      return {
         shares: [],
         clip: null,
         loading: false,
         error: null,
      }
   },

   async created() {
      this.setLoading(true)
      try {
         this.shares = await getAllShares()
      } catch (error) {
         console.error(error)
         this.setError(error)
      } finally {
         this.setLoading(false)
      }
   },

   mounted() {
      this.clip = new Clipboard(".copy-clipboard")
      this.clip.on("success", () => {
         this.$toast.success(this.$t("toasts.linkCopied"))
      })
   },

   beforeUnmount() {
      this.clip.destroy()
   },

   methods: {
      humanTime,
      ...mapActions(useMainStore, ["showHover"]),

      setLoading(value) {
        this.loading = value
      },
      setError(value) {
        this.error = value
      },
      async deleteLink(event, share) {
         event.preventDefault()

         if (event.ctrlKey) {
            await deleteShare(share.token)
            this.shares = this.shares.filter((item) => item.token !== share.token)
            this.$toast.success(this.$t("toasts.shareDeleted"))
         } else {
            this.showHover({
               prompt: "shareDelete",
               confirm: async () => {
                  await deleteShare(share.token)
                  this.shares = this.shares.filter((item) => item.token !== share.token)
                  this.$toast.success(this.$t("toasts.shareDeleted"))
               }
            })
         }
      },

      buildLink(share) {
         let route = this.$router.resolve({ name: "Share", params: { token: share.token } })
         return new URL(route.href, window.location.origin).href
      },

      async showInfo(event, share) {
         let visits = await getShareVisits(share.token)
         this.showHover({
            prompt: "ShareVisits",
            props: { share, visits }
         })
      }
   }
}
</script>
<style>
.empty-state {
   display: flex;
   flex-direction: column;
   align-items: center;
   justify-content: center;
   padding: 40px 20px;
   text-align: center;
   color: var(--textPrimary);
}

.empty-icon i {
   font-size: 48px;
   color: var(--textPrimary);
   margin-bottom: 10px;
}

.empty-title {
   margin: 10px 0 5px;
   font-weight: 500;
}

.empty-desc {
   margin-bottom: 20px;
   max-width: 300px;
   color: var(--textSecondary);
}
</style>