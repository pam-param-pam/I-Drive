<template>
   <errors v-if="error" :error="error" />
   <div v-else-if="!loading" class="row">
      <div class="column">
         <div class="card">
            <div class="card-title">
               <h2>{{ $t('settings.shareManagement') }}</h2>
            </div>

            <div v-if="shares.length > 0" class="card-content full">
               <table>
                  <tr>
                     <th>{{ $t('settings.name') }}</th>
                     <th class="expiry-column">{{ $t('settings.shareExpiry') }}</th>
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
                        <template v-else>{{ $t('permanent') }}</template>
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
            <h2 v-else class="message">
               <i class="material-icons">sentiment_dissatisfied</i>
               <span>{{ $t('files.lonely') }}</span>
            </h2>
         </div>
      </div>
   </div>
</template>

<script>
import Clipboard from 'clipboard'
import { getAllShares, deleteShare } from '@/api/share.js'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import Errors from '@/components/Errors.vue'
import dayjs from "@/utils/dayjsSetup.js"

export default {
   name: 'shares',

   components: {
      Errors
   },

   computed: mapState(useMainStore, ['settings', 'loading', 'error']),

   data() {
      return {
         shares: [],
         clip: null
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
      this.clip = new Clipboard('.copy-clipboard')
      this.clip.on('success', () => {
         this.$toast.success(this.$t('toasts.linkCopied'))
      })
   },

   beforeUnmount() {
      this.clip.destroy()
   },

   methods: {
      ...mapActions(useMainStore, ['setLoading', 'closeHover', 'showHover', 'setError']),

      async deleteLink(event, share) {
         event.preventDefault()

         if (event.ctrlKey) {
            await deleteShare(share.token)
            this.shares = this.shares.filter((item) => item.token !== share.token)
            this.$toast.success(this.$t('toasts.shareDeleted'))
         } else {
            this.showHover({
               prompt: 'shareDelete',
               confirm: async () => {
                  await deleteShare(share.token)
                  this.shares = this.shares.filter((item) => item.token !== share.token)
                  this.$toast.success(this.$t('toasts.shareDeleted'))
               }
            })
         }
      },
      humanTime(time) {
         return dayjs(time, 'YYYY-MM-DD HH:mm').fromNow()
      },

      buildLink(share) {
         let route = this.$router.resolve({ name: 'Share', params: { token: share.token } })
         return new URL(route.href, window.location.origin).href
      },

      showInfo(event, share) {
         this.showHover({
            prompt: "shareAccesses",
            props: {share},
         })
      }
   }
}
</script>
