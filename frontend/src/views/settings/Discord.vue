<template>
  <div class="row" v-if="!loading">
    <div class="column">
      <div class="cards-wrapper">
        <!--        START OF WEBHOOKS CARD-->
        <div v-if="canAddBotsOrWebhooks" class="card">
          <div class="card-title">
            <h2>{{ $t("settings.webhooks") }}</h2>
          </div>
          <div class="card-content">
            <div v-if="webhooks.length > 0" class="table-wrapper">
              <table>
                <tr>
                  <th>#</th>
                  <th>{{ $t("settings.name") }}</th>
                  <th class="expiry-column">{{ $t("settings.createdAt") }}</th>
                  <th></th>
                </tr>

                <tr v-for="(webhook, index) in webhooks" :key="webhook.discord_id">
                  <td>{{ index + 1 }}</td>
                  <td class="share-name-column">
                    <a>{{ webhook.name }}</a>
                  </td>
                  <td class="expiry-column">
                    <a>{{ webhook.created_at }}</a>
                  </td>
                  <td class="small">
                    <button
                      class="action"
                      @click="removeWebhook(webhook.discord_id)"
                      :aria-label="$t('buttons.delete')"
                      :title="$t('buttons.delete')"
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
              <br>
              <br>
              {{ $t("settings.webhookAdvice") }}
            </span>
            </div>
            <input
              v-if="showWebhookInput || webhooks.length === 0"
              v-model="webhookUrl"
              type="text"
              :placeholder="$t('settings.newWebhookPlaceholder')"
              class="input"
            />
          </div>
          <div class="card-action">
            <button
              class="button button--flat"
              @click="addWebhook"
              :aria-label="$t('buttons.add')"
              :title="$t('buttons.add')"
            >
              {{ $t("buttons.add") }}
            </button>
          </div>
        </div>
        <!--        START OF UPLOAD DEST CARD-->
        <div class="card">
          <div class="card-title">
            <h2>{{ $t("settings.uploadDestination") }}</h2>
          </div>
          <div class="card-content">
            <h3>{{ $t("settings.guildId") }}</h3>
            <input
              class="input"
              type="text"
              :disabled="canAddBotsOrWebhooks"
              v-model="guildId"
            />

            <h3>{{ $t("settings.channelId") }}</h3>
            <input
              class="input"
              :disabled="canAddBotsOrWebhooks"
              type="text"
              v-model="channelId"
            />
          </div>
          <div class="card-action">
            <button
              class="button button--flat"
              @click="saveUploadDestination"
              :aria-label="$t('buttons.save')"
              :title="$t('buttons.save')"
            >
              {{ $t("buttons.save") }}
            </button>
          </div>
        </div>
        <!--        END OF UPLOAD DEST CARD-->
      </div>
    </div>

    <div v-if="canAddBotsOrWebhooks" class="column">

      <div class="card">
        <div class="card-title">
          <h2>{{ $t("settings.bots") }}</h2>
        </div>
        <div class="card-content">
          <div v-if="bots.length > 0" class="table-wrapper">
            <table>
              <tr>
                <th>#</th>
                <th>{{ $t("settings.name") }}</th>
                <th class="expiry-column">{{ $t("settings.createdAt") }}</th>
                <th></th>
              </tr>

              <tr v-for="(bot, index) in bots" :key="bot.discord_id">
                <td>{{ index + 1 }}</td>
                <td class="share-name-column">
                  <a>{{ bot.name }}</a>
                </td>
                <td class="expiry-column">
                  <a>{{ bot.created_at }}</a>
                </td>
                <td class="small">
                  <button
                    class="action"
                    @click="removeBot(bot.discord_id)"
                    :aria-label="$t('buttons.delete')"
                    :title="$t('buttons.delete')"
                  >
                    <i class="material-icons">delete</i>
                  </button>
                </td>
              </tr>
            </table>
          </div>
          <div v-else class="info">
            <span>
              {{ $t("settings.botInfo") }}
              <br>
              <br>
              {{ $t("settings.botAdvice") }}
            </span>
          </div>
          <input
            v-if="showBotInput || bots.length === 0"
            v-model="botToken"
            type="text"
            :placeholder="$t('settings.newBotPlaceholder')"
            class="input"
          />
        </div>
        <div class="card-action">
          <button
            class="button button--flat"
            @click="addBot"
            :aria-label="$t('buttons.add')"
            :title="$t('buttons.add')"
          >
            {{ $t("buttons.add") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { addDiscordBot, addDiscordWebhook, deleteDiscordBot, deleteDiscordWebhook, getDiscordSettings, updateDiscordSettings } from "@/api/user.js"
import throttle from "lodash.throttle"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"


export default {
   data() {
      return {
         webhooks: [],
         bots: [],
         showWebhookInput: false,
         webhookUrl: "",
         channel_id: null,
         guild_id: null,
         showBotInput: false,
         botToken: "",
         canAddBotsOrWebhooks: false
      }
   },
   computed: mapState(useMainStore, ["loading", "error"]),
   async created() {
      this.setLoading(true)
      let res = await getDiscordSettings()
      this.webhooks = res.webhooks
      this.bots = res.bots
      this.channelId = res.channel_id
      this.guildId = res.guild_id
      this.canAddBotsOrWebhooks = res.can_add_bots_or_webhooks
      this.setLoading(false)

   },
   methods: {
      ...mapActions(useMainStore, ["setLoading", "showHover"]),

      addWebhook: throttle(async function(event) {
         if (this.webhookUrl === "") {
            this.showWebhookInput = true
            return
         }
         let res = await addDiscordWebhook({ webhook_url: this.webhookUrl })
         this.webhookUrl = ""
         this.webhooks.push(res)
         this.showWebhookInput = false
         this.$toast.success(this.$t("toasts.webhookAdded"))

      }, 1000),


      addBot: throttle(async function(event) {
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

      async removeWebhook(discord_id) {
         await deleteDiscordWebhook({ "discord_id": discord_id })
         this.webhooks = this.webhooks.filter(webhook => webhook.discord_id !== discord_id)
         this.$toast.success(this.$t("toasts.webhookDeleted"))

      },

      async removeBot(discord_id) {
         await deleteDiscordBot({ "discord_id": discord_id })
         this.bots = this.bots.filter(webhook => webhook.discord_id !== discord_id)
         this.$toast.success(this.$t("toasts.botDeleted"))
      },

      async saveUploadDestination() {
         this.showHover({
            prompt: "UploadDestinationWarning",
            confirm: async () => {
               await updateDiscordSettings({"channel_id": this.channel_id, "guild_id": this.guild_id})
               this.$toast.success(this.$t("toasts.uploadDestinationUpdated"))
            },
         })
      }

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
</style>
