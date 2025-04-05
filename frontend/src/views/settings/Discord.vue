<template>
   <errors v-if="error" :error="error" />
   <div v-else-if="!loading" class="row">
      <div class="column">
         <div class="cards-wrapper">
            <!--        START OF WEBHOOKS CARD-->
            <div v-if="canAddBotsOrWebhooks" class="card">
               <div class="card-title">
                  <h2>{{ $t('settings.webhooks') }}</h2>
               </div>
               <div class="card-content">
                  <div v-if="webhooks.length > 0" class="table-wrapper">
                     <table>
                        <tr>
                           <th>{{ '# &#8205; &#8205; &#8205; &#8205;' + $t('settings.name') }}</th>
                           <th class="expiry-column">{{ $t('settings.addedAt') }}</th>
                           <th></th>
                        </tr>

                        <tr v-for="(webhook, index) in webhooks" :key="webhook.discord_id">
                           <td class="share-name-column">
                              <a>{{
                                 index + 1 + ' &#8205; &#8205; &#8205; &#8205;' + webhook.name
                              }}</a>
                           </td>
                           <td class="expiry-column">
                              <a>{{ webhook.created_at }}</a>
                           </td>
                           <td class="small">
                              <button
                                 :aria-label="$t('buttons.delete')"
                                 :title="$t('buttons.delete')"
                                 class="action"
                                 @click="deleteWebhook(webhook.discord_id)"
                              >
                                 <i class="material-icons">delete</i>
                              </button>
                           </td>
                        </tr>
                     </table>
                  </div>
                  <div v-else class="info">
                     <span>
                        {{ $t('settings.webhookInfo') }}
                        <br />
                        <br />
                        {{ $t('settings.webhookAdvice') }}
                     </span>
                  </div>
                  <input
                     v-if="showWebhookInput || webhooks.length === 0"
                     v-model="webhookUrl"
                     :placeholder="$t('settings.newWebhookPlaceholder')"
                     class="input"
                     type="text"
                  />
               </div>
               <div class="card-action">
                  <button
                     :aria-label="$t('buttons.add')"
                     :title="$t('buttons.add')"
                     class="button button--flat"
                     @click="addWebhook"
                  >
                     {{ $t('buttons.add') }}
                  </button>
               </div>
            </div>
            <!--        START OF UPLOAD DEST CARD-->
            <div class="card">
               <div class="card-title">
                  <h2>{{ $t('settings.uploadDestination') }}</h2>
               </div>
               <div class="card-content">
                  <h3>{{ $t('settings.guildId') }}</h3>
                  <input
                     v-model="guildId"
                     :disabled="uploadDestinationLocked"
                     class="input"
                     type="text"
                  />

                  <h3>{{ $t('settings.channelId') }}</h3>
                  <input
                     v-model="channelId"
                     :disabled="uploadDestinationLocked"
                     class="input"
                     type="text"
                  />
                  <h3>{{ $t('settings.attachmentName') }}</h3>
                  <input v-model="attachmentName" class="input" type="text" />
               </div>
               <div class="card-action">
                  <button
                     :aria-label="$t('buttons.save')"
                     :title="$t('buttons.save')"
                     class="button button--flat"
                     @click="saveUploadDestination"
                  >
                     {{ $t('buttons.save') }}
                  </button>
               </div>
            </div>
            <!--        END OF UPLOAD DEST CARD-->
         </div>
      </div>

      <div v-if="canAddBotsOrWebhooks" class="column">
         <div class="card">
            <div class="card-title">
               <h2>{{ $t('settings.bots') }}</h2>
            </div>
            <div class="card-content">
               <div v-if="bots.length > 0" class="table-wrapper">
                  <table>
                     <tr>
                        <th>{{ '# &#8205; &#8205; &#8205; &#8205;' + $t('settings.name') }}</th>
                        <th class="expiry-column">{{ $t('settings.addedAt') }}</th>
                        <th></th>
                     </tr>

                     <tr
                        v-for="(bot, index) in bots"
                        :key="bot.discord_id"
                        :class="{ disabled: bot.disabled }"
                     >
                        <td
                           v-if="bot.disabled"
                           v-tooltip="$t('settings.botDisabledNoPerms')"
                           class="share-name-column"
                        >
                           <a>{{ index + 1 + ' &#8205; &#8205; &#8205; &#8205;' + bot.name }}</a>
                        </td>
                        <td v-else class="share-name-column">
                           <a>{{ index + 1 + ' &#8205; &#8205; &#8205; &#8205;' + bot.name }}</a>
                        </td>
                        <td class="expiry-column">
                           <a>{{ bot.created_at }}</a>
                        </td>
                        <td v-if="bot.disabled" class="small">
                           <button
                              :aria-label="$t('buttons.retry')"
                              :title="$t('buttons.retry')"
                              class="action"
                              @click="enableBot(bot.discord_id)"
                           >
                              <i class="material-icons">sync</i>
                           </button>
                        </td>
                        <td v-else class="small" />
                        <td class="small">
                           <button
                              :aria-label="$t('buttons.delete')"
                              :title="$t('buttons.delete')"
                              class="action"
                              @click="deleteBot(bot.discord_id)"
                           >
                              <i class="material-icons">delete</i>
                           </button>
                        </td>
                     </tr>
                  </table>
               </div>
               <div v-else class="info">
                  <span>
                     {{ $t('settings.botInfo') }}
                     <br />
                     <br />
                     {{ $t('settings.botAdvice') }}
                  </span>
               </div>
               <input
                  v-if="showBotInput || bots.length === 0"
                  v-model="botToken"
                  :placeholder="$t('settings.newBotPlaceholder')"
                  class="input"
                  type="text"
               />
            </div>
            <div class="card-action">
               <button
                  :aria-label="$t('buttons.add')"
                  :title="$t('buttons.add')"
                  class="button button--flat"
                  @click="addBot"
               >
                  {{ $t('buttons.add') }}
               </button>
            </div>
         </div>
      </div>
   </div>
</template>

<script>
import {
   addDiscordBot,
   addDiscordWebhook,
   deleteDiscordBot,
   deleteDiscordWebhook,
   enableDiscordBot,
   getDiscordSettings,
   updateDiscordSettings
} from '@/api/user.js'
import throttle from 'lodash.throttle'
import { mapActions, mapState } from 'pinia'
import { useMainStore } from '@/stores/mainStore.js'
import { useUploadStore } from '@/stores/uploadStore.js'
import Errors from "@/components/Errors.vue"
import { getAllShares } from "@/api/share.js"

export default {
   components: { Errors },
   data() {
      return {
         bots: [],
         showWebhookInput: false,
         webhookUrl: '',
         channel_id: null,
         guildId: null,
         showBotInput: false,
         botToken: '',
         attachmentName: '',
         canAddBotsOrWebhooks: false,
         canChangeUploadDestination: false,

         res: null
      }
   },

   computed: {
      ...mapState(useMainStore, ['loading', 'error', 'webhooks']),
      ...mapState(useUploadStore, ['webhooks'])
   },

   async created() {
      this.setLoading(true)
      try {
         let res = await getDiscordSettings()
         this.setWebhooks(res.webhooks)

         this.bots = res.bots
         this.channelId = res.channel_id
         this.guildId = res.guild_id
         this.attachmentName = res.attachment_name
         this.canAddBotsOrWebhooks = res.can_add_bots_or_webhooks
         this.uploadDestinationLocked = res.upload_destination_locked
         this.res = res
      } catch (error) {
         console.error(error)
         this.setError(error)
      } finally {
         this.setLoading(false)
      }

   },

   methods: {
      ...mapActions(useMainStore, ['setError', 'setLoading', 'showHover', 'setWebhooks', 'removeWebhook', 'addToWebhooks']),

      ...mapActions(useUploadStore, ['setWebhooks', 'removeWebhook', 'addToWebhooks']),

      addWebhook: throttle(async function () {
         if (this.webhookUrl === '') {
            this.showWebhookInput = true
            return
         }
         let res = await addDiscordWebhook({ webhook_url: this.webhookUrl })

         this.webhookUrl = ''

         this.addToWebhooks(res)
         this.showWebhookInput = false
         this.$toast.success(this.$t('toasts.webhookAdded'))
      }, 1000),

      addBot: throttle(async function () {
         if (this.botToken === '') {
            this.showBotInput = true
            return
         }
         let res = await addDiscordBot({ token: this.botToken })
         this.botToken = ''
         this.bots.push(res)
         this.showBotInput = false
         this.$toast.success(this.$t('toasts.botAdded'))
      }, 1000),

      deleteWebhook: throttle(async function (discord_id) {
         await deleteDiscordWebhook({ discord_id: discord_id })
         this.removeWebhook(discord_id)
         this.$toast.success(this.$t('toasts.webhookDeleted'))
      }, 1000),

      enableBot: throttle(async function (discord_id) {
         await enableDiscordBot({ discord_id: discord_id })
         let bot = this.bots.find((bot) => bot.discord_id === discord_id)
         if (bot) {
            bot.disabled = false
         }
         this.$toast.success(this.$t('toasts.botEnabled'))
      }, 1000),

      deleteBot: throttle(async function (discord_id) {
         await deleteDiscordBot({ discord_id: discord_id })
         this.bots = this.bots.filter((webhook) => webhook.discord_id !== discord_id)
         this.$toast.success(this.$t('toasts.botDeleted'))
      }, 1000),

      saveUploadDestination: throttle(async function () {
         if (this.res.guild_id !== this.guildId || this.res.channel_id !== this.channelId) {
            this.showHover({
               prompt: 'UploadDestinationWarning',
               confirm: async () => {
                  let res = await updateDiscordSettings({
                     channel_id: this.channelId,
                     guild_id: this.guildId,
                     attachment_name: this.attachmentName
                  })
                  this.$toast.success(this.$t('toasts.uploadDestinationUpdated'))
                  this.canAddBotsOrWebhooks = res.can_add_bots_or_webhooks
                  this.uploadDestinationLocked = res.upload_destination_locked
                  console.log(this.uploadDestinationLocked)
                  console.log(this.canAddBotsOrWebhooks)
               }
            })
         } else {
            await updateDiscordSettings({
               channel_id: this.channelId,
               guild_id: this.guildId,
               attachment_name: this.attachmentName
            })
            this.$toast.success(this.$t('toasts.uploadDestinationUpdated'))
         }
      }, 1000)
   }
}
</script>

<style scoped>
.table-wrapper {
   padding-bottom: 1em;
}

.button {
   padding: 8px 12px;
   border: none;
   border-radius: 4px;
   cursor: pointer;
}

.info {
   padding-bottom: 1em;
}

.input:disabled {
   color: gray;
}

.input:disabled:hover {
   cursor: not-allowed;
}

.cards-wrapper {
   width: 100%;
}

.disabled {
   color: gray;
}

.expiry-column {
   max-width: 50px;
}
</style>
