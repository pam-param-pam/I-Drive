<template>
   <errors v-if="error" :error="error" />
   <div v-else-if="!loading" class="row">
      <!-- COLUMN 1 -->
      <div class="column">
         <div class="cards-wrapper">

            <!-- AUTO SETUP CARD -->
            <div v-if="!autoSetupComplete" class="card">
               <div class="card-title">
                  <h2>{{ $t("settings.autoSetup") }}</h2>
               </div>
               <div class="card-content">
                  <h3>{{ $t("settings.guildId") }}</h3>
                  <input
                     v-model="guildId"
                     :placeholder="$t('settings.enterGuildId')"
                     class="input"
                     type="text"
                     @keyup.enter="doAutoSetup"
                  />
                  <h3>{{ $t("settings.primaryBot") }}</h3>
                  <input
                     v-model="botToken"
                     :placeholder="$t('settings.enterBotToken')"
                     class="input"
                     type="text"
                     @keyup.enter="doAutoSetup"
                  />
                  <h3>{{ $t("settings.attachmentName") }}</h3>
                  <input
                     v-model="attachmentName"
                     :placeholder="$t('settings.enterAttachmentName')"
                     class="input"
                     type="text"
                     @keyup.enter="doAutoSetup"
                  />
               </div>
               <div class="card-action">
                  <button
                     :aria-label="$t('buttons.autoSetup')"
                     :title="$t('buttons.autoSetup')"
                     class="button button--flat"
                     @click="doAutoSetup"
                  >
                     {{ $t("buttons.autoSetup") }}
                  </button>
               </div>
            </div>
            <!--        START OF WEBHOOKS CARD-->
            <div v-if="autoSetupComplete" class="card">
               <div class="card-title">
                  <h2>{{ $t("settings.webhooks") }}</h2>
               </div>
               <div class="card-content">
                  <div v-if="webhooks.length > 0" class="table-wrapper">
                     <table>
                        <tr>
                           <th>{{ "# &#8205; &#8205; &#8205; &#8205;" + $t("settings.name") }}</th>
                           <th class="channel-column">{{ $t("settings.channel") }}</th>
                           <th class="expiry-column">{{ $t("settings.addedAt") }}</th>
                           <th></th>
                        </tr>

                        <tr v-for="(webhook, index) in webhooks" :key="webhook.discord_id">
                           <td class="share-name-column">
                              <a>{{
                                  index + 1 + " &#8205; &#8205; &#8205; &#8205;" + webhook.name
                                 }}</a>
                           </td>
                           <td class="share-name-column channel-column">
                              <a>{{ webhook.channel.name }}</a>
                           </td>
                           <td class="share-name-column expiry-column">
                              <a>{{ humanTime(webhook.created_at) }}</a>
                           </td>
                           <td class="share-name-column small">
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
                {{ $t("settings.webhookInfo") }}
                <br />
                <br />
                {{ $t("settings.webhookAdvice") }}
             </span>
                  </div>
                  <input
                     v-if="showWebhookInput || webhooks.length === 0"
                     v-model="webhookUrl"
                     :placeholder="$t('settings.newWebhookPlaceholder')"
                     class="input"
                     type="text"
                     @keyup.enter="addWebhook"
                  />
               </div>
               <div class="card-action">
                  <button
                     :aria-label="$t('buttons.add')"
                     :title="$t('buttons.add')"
                     class="button button--flat"
                     @click="addWebhook"
                  >
                     {{ $t("buttons.add") }}
                  </button>
               </div>
            </div>

            <!--        START OF UPLOAD DEST CARD-->
            <div v-if="autoSetupComplete" class="card">
               <div class="card-title">
                  <h2>{{ $t("settings.uploadDestination") }}</h2>
               </div>
               <div class="card-content">
                  <h3>{{ $t("settings.guildId") }}</h3>
                  <input
                     v-model="guildId"
                     :disabled="autoSetupComplete"
                     class="input"
                     type="text"
                  />

                  <h3>{{ $t("settings.attachmentName") }}</h3>
                  <input
                     v-model="attachmentName"
                     class="input"
                     type="text"
                     @keyup.enter="updateAttachmentName"
                  />
               </div>
               <div class="card-action">
                  <button
                     :aria-label="$t('buttons.reset')"
                     :title="$t('buttons.reset')"
                     class="button button--flat button--red"
                     @click="resetAll"
                  >
                     {{ $t("buttons.reset") }}
                  </button>

                  <button
                     :aria-label="$t('buttons.save')"
                     :title="$t('buttons.save')"
                     class="button button--flat"
                     @click="updateAttachmentName"
                  >
                     {{ $t("buttons.save") }}
                  </button>

               </div>
            </div>
         </div>
      </div>
      <!-- COLUMN 2 -->
      <div v-if="autoSetupComplete" class="column">
         <div class="cards-wrapper">

            <!--        START OF BOTS CARD      -->
            <div class="card">
               <div class="card-title">
                  <h2>{{ $t("settings.bots") }}</h2>
               </div>
               <div class="card-content">
                  <div v-if="bots.length > 0" class="table-wrapper">
                     <table>
                        <tr>
                           <th>{{ "# &#8205; &#8205; &#8205; &#8205;" + $t("settings.name") }}</th>
                           <th class="expiry-column">{{ $t("settings.addedAt") }}</th>
                           <th></th>
                        </tr>

                        <tr
                           v-for="(bot, index) in bots"
                           :key="bot.discord_id"
                        >
                           <td class="share-name-column">
                              <a>{{ index + 1 + " &#8205; &#8205; &#8205; &#8205;" + bot.name }}</a>
                              <span v-if="bot.primary" :title="$t('settings.primaryBot')">
                     <svg class="crown-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24"
                          style="vertical-align: text-bottom;">
                      <path fill="currentColor"
                            d="M5 18a1 1 0 0 0-1 1 3 3 0 0 0 3 3h10a3 3 0 0 0 3-3 1 1 0 0 0-1-1H5ZM3.04 7.76a1 1 0 0 0-1.52 1.15l2.25 6.42a1 1 0 0 0 .94.67h14.55a1 1 0 0 0 .95-.71l1.94-6.45a1 1 0 0 0-1.55-1.1l-4.11 3-3.55-5.33.82-.82a.83.83 0 0 0 0-1.18l-1.17-1.17a.83.83 0 0 0-1.18 0l-1.17 1.17a.83.83 0 0 0 0 1.18l.82.82-3.61 5.42-4.41-3.07Z"></path>
                    </svg>
                  </span>

                           </td>
                           <td class="share-name-column expiry-column">
                              <a>{{ humanTime(bot.created_at) }}</a>
                           </td>
                           <td class="share-name-column small">
                              <button
                                 :aria-label="$t('buttons.delete')"
                                 :title="$t('buttons.delete')"
                                 :disabled="bot.primary"
                                 class="action"
                                 @click="deleteBot(bot.discord_id)"
                              >
                                 <i class="material-icons">delete</i>
                              </button>
                           </td>
                        </tr>
                     </table>
                  </div>
                  <div v-if="bots.length < 5" class="info">
                  <span>
                     {{ $t("settings.botInfo") }}
                     <br />
                     <br />
                     {{ $t("settings.botAdvice") }}
                  </span>
                  </div>
                  <input
                     v-if="showBotInput || bots.length === 0"
                     v-model="botToken"
                     :placeholder="$t('settings.newBotPlaceholder')"
                     class="input"
                     type="text"
                     @keyup.enter="addBot"
                  />
               </div>
               <div class="card-action">
                  <button
                     :aria-label="$t('buttons.add')"
                     :title="$t('buttons.add')"
                     class="button button--flat"
                     @click="addBot"
                  >
                     {{ $t("buttons.add") }}
                  </button>
               </div>
            </div>
         </div>
      </div>
   </div>
</template>

<script>
import {
   addDiscordBot,
   addDiscordWebhook,
   autoSetup,
   deleteDiscordBot,
   deleteDiscordSettings,
   deleteDiscordWebhook,
   getDiscordSettings,
   updateDiscordSettings
} from "@/api/user.js"
import throttle from "lodash.throttle"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import Errors from "@/components/Errors.vue"
import { humanTime } from "@/utils/common.js"

export default {
   components: { Errors },
   data() {
      return {
         bots: [],
         channels: [],
         autoSetupComplete: false,

         webhookUrl: "",
         guildId: "",
         botToken: "",
         attachmentName: "ala",

         showBotInput: false,
         showWebhookInput: false,
         res: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["loading", "error", "settings"]),
      ...mapState(useUploadStore, ["webhooks"])
   },

   async created() {
      this.setLoading(true)
      try {
         let res = await getDiscordSettings()
         this.setDiscordSettings(res)
      } catch (error) {
         console.error(error)
         this.setError(error)
      } finally {
         this.setLoading(false)
      }
   },

   methods: {
      humanTime,
      ...mapActions(useMainStore, ["setError", "setLoading", "showHover", "setWebhooks", "removeWebhook", "addToWebhooks"]),

      ...mapActions(useUploadStore, ["setWebhooks", "removeWebhook", "addToWebhooks"]),
      setDiscordSettings(res) {
         this.setWebhooks(res.webhooks)

         this.bots = res.bots
         this.guildId = res.guild_id
         this.webhooks = res.webhooks
         this.attachmentName = res.attachment_name
         this.autoSetupComplete = res.auto_setup_complete
         this.channels = res.channels
         this.res = res
      },
      addWebhook: throttle(async function() {
         if (this.webhookUrl === "") {
            this.showWebhookInput = true
            return
         }
         let res = await addDiscordWebhook({ webhook_url: this.webhookUrl })

         this.webhookUrl = ""

         this.addToWebhooks(res)
         this.showWebhookInput = false
         this.$toast.success(this.$t("toasts.webhookAdded"))
      }, 1000),

      addBot: throttle(async function() {
         if (this.botToken === "") {
            this.showBotInput = true
            return
         }
         let res = await addDiscordBot({ token: this.botToken })
         this.botToken = ""
         this.bots.push(res)
         this.showBotInput = false
         this.$toast.success(this.$t("toasts.botAdded"))
      }, 1000),

      deleteWebhook: throttle(async function(discord_id) {
         await deleteDiscordWebhook(discord_id)
         this.removeWebhook(discord_id)
         this.$toast.success(this.$t("toasts.webhookDeleted"))
      }, 1000),

      deleteBot: throttle(async function(discord_id) {
         await deleteDiscordBot(discord_id)
         this.bots = this.bots.filter((webhook) => webhook.discord_id !== discord_id)
         this.$toast.success(this.$t("toasts.botDeleted"))
      }, 1000),

      async resetAll() {
         const toastId = this.$toast.info(this.$t("toasts.discordSettingsDeleting"),
           { type: "info", timeout: null, draggable: false, closeOnClick: false, closeButton: false }
         )

         try {
            let res = await deleteDiscordSettings()

            let isError = res.errors
            let content = isError ? res.errors : this.$t("toasts.discordSettingsDeleted")
            let type    = isError ? "error" : "success"
            let timeout = isError ? null : 3000

            this.$toast.update(toastId, {
               content,
               options: { type, timeout }
            }, true)

            this.setDiscordSettings(res.settings)
         } catch (err) {
            console.error(err)
            this.$toast.dismiss(toastId)
         }
      },
      async doAutoSetup() {
         if (!this.guildId || !this.botToken || !this.attachmentName) {
            this.$toast.error(this.$t("toasts.fillAllFields"))
            return
         }
         this.showHover({
            prompt: "UploadDestinationWarning",
            confirm: async () => {
               let toastId = this.$toast.info(this.$t("toasts.autoSetupInProgress"), {
                  type: "info", timeout: null, draggable: false, closeOnClick: false, closeButton: false
               })
               try {
                  let res = await autoSetup({ "guild_id": this.guildId, "bot_token": this.botToken, "attachment_name": this.attachmentName })

                  this.$toast.update(toastId, {
                     content: this.$t("toasts.autoSetupComplete"),
                     options: { type: "success", timeout: 3000 }
                  }, true)

                  this.setDiscordSettings(res)
               } catch (e) {
                  console.error(e)
                  this.$toast.dismiss(toastId)
               }

            }
         })
      },
      updateAttachmentName: throttle(async function() {
         await updateDiscordSettings({ attachment_name: this.attachmentName })
         this.$toast.success(this.$t("toasts.uploadDestinationUpdated"))
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

.channel-column {
 max-width: 50px;
}

.expiry-column {
 max-width: 50px;
 white-space: nowrap;
}

.crown-icon {
 margin-left: 4px;
 margin-bottom: 1px;
 height: 1em;
 vertical-align: middle;
 color: #d6ac82;
}
</style>
