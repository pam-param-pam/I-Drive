<template>
  <div class="row">
    <div class="column">
      <form class="card" @submit.prevent="saveWebhooks">
        <div class="card-title">
          <h2>{{ $t("settings.webhooks") }}</h2>
        </div>
        <div class="card-content">

            <div v-for="(webhook, index) in webhooks" :key="index" class="list-item">
              <p>{{ webhook.name }}</p>

              <button
                class="action"
                @click="deleteLink($event, share)"
                :aria-label="$t('buttons.delete')"
                :title="$t('buttons.delete')"
              >
                <i class="material-icons">delete</i>
              </button>
            </div>
          <input
            v-model="newWebhook"
            type="text"
            placeholder="Webhook URL"
            class="input"
          />

        </div>
        <div class="card-action">
          <input
            class="button button--flat"
            type="submit"
            :value="$t('buttons.update')"
          />
        </div>
      </form>
    </div>

    <div class="column">
      <form class="card" @submit.prevent="saveTokens">
        <div class="card-title">
          <h2>{{ $t("settings.tokens") }}</h2>
        </div>
        <div class="card-content">
          <ul>
            <li v-for="(token, index) in tokens" :key="index" class="list-item">
              <input
                v-model="token.guildId"
                type="text"
                placeholder="Guild ID"
                class="input-field"
              />
              <input
                v-model="token.value"
                type="text"
                placeholder="Token Value"
                class="input-field"
              />
              <button type="button" @click="removeToken(index)" class="button button--remove">
                {{ $t("buttons.remove") }}
              </button>
            </li>
          </ul>
          <button type="button" @click="addToken" class="button button--add">
            {{ $t("buttons.addToken") }}
          </button>
        </div>
        <div class="card-action">
          <input
            class="button button--flat"
            type="submit"
            :value="$t('buttons.update')"
          />
        </div>
      </form>
    </div>


  </div>
</template>

<script>
export default {
   data() {
      return {
         webhooks: [{"name": "captain hook"}],
         tokens: []
      };
   },
   methods: {
      addWebhook() {
         this.webhooks.push({ guildId: "", url: "" });
      },
      removeWebhook(index) {
         this.webhooks.splice(index, 1);
      },
      saveWebhooks() {
         // Logic to save webhooks
         console.log("Webhooks saved", this.webhooks);
      },
      addToken() {
         this.tokens.push({ guildId: "", value: "" });
      },
      removeToken(index) {
         this.tokens.splice(index, 1);
      },
      saveTokens() {
         // Logic to save tokens
         console.log("Tokens saved", this.tokens);
      }
   }
};
</script>

<style scoped>

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



.button:hover {
 opacity: 0.9;
}
</style>
