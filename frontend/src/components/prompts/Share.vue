<template>
   <div id="share" class="card floating share__promt__card">
      <div class="card-title">
         <h2>{{ $t('buttons.share') }}</h2>
      </div>

      <template v-if="listing">
         <div class="card-content">
            <div class="share-table-container">
               <table>
                  <tr>
                     <th>#</th>
                     <th>{{ $t('settings.shareExpiry') }}</th>
                     <th></th>
                     <th></th>
                  </tr>

                  <tr v-for="(link, index) in links" :key="link.id">
                     <td>{{ index + 1 }}</td>
                     <td>
                        {{ humanTime(link.expire) }}
                     </td>
                     <td class="small">
                        <button
                           :aria-label="$t('buttons.copyToClipboard')"
                           :data-clipboard-text="buildLink(link)"
                           :title="$t('buttons.copyToClipboard')"
                           class="action copy-clipboard"
                        >
                           <i class="material-icons">content_paste</i>
                        </button>
                     </td>
                     <td class="small">
                        <button
                           :aria-label="$t('buttons.delete')"
                           :title="$t('buttons.delete')"
                           class="action"
                           @click="deleteLink($event, link)"
                        >
                           <i class="material-icons">delete</i>
                        </button>
                     </td>
                  </tr>
               </table>
            </div>
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
            <button
               :aria-label="$t('buttons.new')"
               :title="$t('buttons.new')"
               class="button button--flat button--blue"
               @click="() => switchListing()"
            >
               {{ $t('buttons.new') }}
            </button>
         </div>
      </template>

      <template v-else>
         <div class="card-content">
            <p>{{ $t('prompts.shareDuration') }}</p>
            <div class="input-group input">
               <input v-focus v-model.trim="time" max="2147483647" min="1" type="number" />
               <select v-model="unit" :aria-label="$t('time.unit')" class="right">
                  <option value="minutes">{{ $t('time.minutes') }}</option>
                  <option value="hours">{{ $t('time.hours') }}</option>
                  <option value="days">{{ $t('time.days') }}</option>
               </select>
            </div>
            <p>{{ $t('prompts.optionalPassword') }}</p>
            <input v-model.trim="password" class="input input--block" />
         </div>

         <div class="card-action">
            <button
               :aria-label="$t('buttons.cancel')"
               :title="$t('buttons.cancel')"
               class="button button--flat button--grey"
               @click="() => switchListing()"
            >
               {{ $t('buttons.cancel') }}
            </button>
            <button
               :aria-label="$t('buttons.share')"
               :title="$t('buttons.share')"
               class="button button--flat button--blue"
               @click="submit"
            >
               {{ $t('buttons.share') }}
            </button>
         </div>
      </template>
   </div>
</template>

<script>
import moment from 'moment/min/moment-with-locales.js'
import Clipboard from 'clipboard'
import { createShare, getAllShares, removeShare } from '@/api/share.js'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import throttle from 'lodash.throttle'

export default {
   name: 'share',

   data() {
      return {
         time: 7,
         unit: 'days',
         links: [],
         clip: null,
         password: '',
         listing: true
      }
   },

   computed: {
      ...mapState(useMainStore, ['selected', 'settings'])
   },

   async mounted() {
      this.clip = new Clipboard('.copy-clipboard')
      this.clip.on('success', () => {
         this.$toast.success(this.$t('toasts.linkCopied'))
      })
      await this.fetchShares()
   },

   beforeUnmount() {
      this.clip.destroy()
   },

   methods: {
      ...mapActions(useMainStore, ['closeHover', 'showHover']),

      async fetchShares() {
         let links = await getAllShares()

         links = links.filter((item) => item.resource_id === this.selected[0].id)

         this.links = links
         this.sort()

         if (this.links.length === 0) {
            this.listing = false
         }
      },

      submit: throttle(async function (event) {
         if (this.listing) return
         let res = await createShare({
            resource_id: this.selected[0].id,
            password: this.password,
            value: this.time,
            unit: this.unit
         })
         this.links.push(res)
         this.sort()

         this.time = 7
         this.unit = 'days'
         this.password = ''

         this.$toast.success(this.$root.$t('settings.shareCreated'))

         this.listing = true
      }, 1000),

      async deleteLink(event, share) {
         event.preventDefault()

         await removeShare({ token: share.token })
         this.links = this.links.filter((item) => item.id !== share.id)
         this.$toast.success(this.$t('settings.shareDeleted'))
         if (this.links.length === 0) {
            this.listing = false
         }
      },

      humanTime(time) {
         //todo czm globalny local nie działa?
         let locale = this.settings?.locale || 'en'

         moment.locale(locale)

         // Parse the target date
         return moment(time, 'YYYY-MM-DD HH:mm').endOf('second').fromNow()
      },

      buildLink(share) {
         let { protocol, host } = window.location
         let base = `${protocol}//${host}`
         return `${base}/share/${share.token}`
      },

      sort() {
         this.links = this.links.sort((a, b) => {
            if (a.expire === 0) return -1
            if (b.expire === 0) return 1
            return new Date(a.expire) - new Date(b.expire)
         })
      },

      switchListing() {
         if (this.links.length === 0 && !this.listing) {
            this.closeHover()
         }

         this.listing = !this.listing
      }
   }
}
</script>
<style scoped>
.share-table-container {
   max-height: 50vh;
   overflow-y: auto;
   overflow-x: hidden;
   padding-right: 0.5em;
}

.share-table-container table {
   width: 100%;
   border-collapse: collapse; /* optional for nicer border */
}

.share-table-container th {
   position: sticky;
   top: 0;
   background: var(--surfacePrimary);
   z-index: 2;
   box-shadow: 0 4px 8px rgba(0, 0, 0, 0.6);

}
</style>