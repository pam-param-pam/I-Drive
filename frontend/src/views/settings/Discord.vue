<template>
  <errors v-if="error" :error="error" />
  <div class="row" v-else-if="!loading">
    <div class="column">
      <div class="card">
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
              {{$t('settings.webhookInfo')}}
              <br>
              <br>
              {{$t('settings.webhookAdvice')}}
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
    </div>

    <div class="column">
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
              {{$t('settings.botInfo')}}
              <br>
              <br>
              {{$t('settings.botAdvice')}}
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
import { addDiscordWebhook, getDiscordSettings } from "@/api/user.js";
import throttle from "lodash.throttle";
import Errors from "@/components/Errors.vue"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"


export default {
   components: { Errors },
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
      };
   },
   computed: mapState(useMainStore, ["loading", "error"]),
   async created() {
      this.setLoading(true)
      let res = await getDiscordSettings();
      this.webhooks = res.webhooks;
      this.bots = res.bots;
      this.channel_id = res.channel_id;
      this.guild_id = res.guild_id;
      this.setLoading(false)

   },
   methods: {
      ...mapActions(useMainStore, ["setLoading", "setError"]),

      addWebhook: throttle(async function (event) {
         if (this.webhookUrl === "") {
            this.showWebhookInput = true;
            return;
         }
         let res = await addDiscordWebhook({ webhook_url: this.webhookUrl });
         this.webhookUrl = "";
         this.webhooks.push(res);
         this.showWebhookInput = false;
      }, 1000),


      addBot: throttle(async function (event) {
         if (this.botToken === "") {
            this.showBotInput = true;
            return;
         }
         // let res = await addDiscordWebhook({ webhook_url: this.webhookUrl });
         this.botToken = "";
         // this.webhooks.push(res);
         this.showBotInput = false;
      }, 1000),


      removeWebhook(index) {
         this.webhooks.splice(index, 1);
      },

      saveWebhooks() {
         console.log("Webhooks saved", this.webhooks);
      },

      removeBot(index) {
         this.bots.splice(index, 1);
      },

      saveBots() {
         console.log("Bots saved", this.bots);
      }
   }
};
</script>

<style scoped>
.table-wrapper {
 padding-bottom: 1em;
}

.list-item {
 display: flex;
 gap: 10px;
 margin-block-end: 0em !important;
}

.button {
 padding: 8px 12px;
 border: none;
 border-radius: 4px;
 cursor: pointer;
}

.button--add {
 background-color: var(--background);
}

.button--remove {
 background-color: var(--dark-red);
}

.info {
 padding-bottom: 1em;
}

.button:hover {
 opacity: 0.9;
}
</style>
