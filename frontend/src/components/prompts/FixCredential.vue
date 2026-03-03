<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t("prompts.fixCredential") }}</h2>
      </div>

      <div class="card-content">
         <p>
            <strong>{{ credentialDisplayName }}</strong>
         </p>

         <div class="block-info">
            <p v-if="credential.blocked_until">
               <strong>{{ $t("prompts.blockedUntil") }}:</strong>
               {{ formattedBlockedUntil }}
            </p>

            <p v-else>
               <strong>{{ $t("prompts.blockedUntil") }}:</strong>
               {{ $t("prompts.permanent") }}
            </p>

            <p v-if="credential.block_reason">
               <strong>{{ $t("prompts.blockReason") }}:</strong>
               {{ credential.block_reason }}
            </p>

            <p v-if="credential.discord_error_code">
               <strong>{{ $t("prompts.discord_error_code") }}:</strong>
               {{ credential.discord_error_code }}
            </p>

            <div class="help-box">
               <p>{{ helpMessage }}</p>
            </div>
         </div>

      </div>

      <div class="card-action">
         <button
            class="button button--flat button--grey"
            @click="cancel()"
         >
            {{ $t("buttons.cancel") }}
         </button>

         <button
            v-if="credential.is_blocked"
            class="button button--flat"
            @click="reenable()"
         >
            {{ $t("buttons.reEnable") }}
         </button>
      </div>
   </div>
</template>
<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { reenableCredential } from "@/api/user.js"

export default {
   name: "FixCredential",

   props: {
      credential: {
         type: Object,
         required: true
      }
   },
   created() {
      console.log(this.credential)
   },
   computed: {
      ...mapState(useMainStore, ["currentPrompt"]),

      credentialDisplayName() {
         return this.credential.name
      },

      formattedBlockedUntil() {
         if (!this.credential.blocked_until) return null
         return new Date(this.credential.blocked_until * 1000).toLocaleString()
      },

      helpMessage() {
         const code = this.credential.discord_error_code

         if (!code)
            return this.$t("help.generic")

         switch (code) {

            case 40001: // Unauthorized
            case 40014: // Invalid token
               return this.$t("help.invalidToken")

            case 50013: // Missing Permissions
            case 50001: // Missing Access
               return this.$t("help.missingPermission")

            case 10004: // Unknown Guild
               return this.$t("help.unknownGuild")

            case 10015: // Unknown Webhook
               return this.$t("help.webhookDeleted")

            case 10003: // Unknown Channel
               return this.$t("help.unknownChannel")

            case 20028: // Channel write rate limit
            case 20029: // Server write rate limit
               return this.$t("help.rateLimit")

            default:
               return this.$t("help.generic")
         }
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "setError"]),

      async reenable() {
         await reenableCredential({"credential_id": this.credential.discord_id})
         this.$toast.success(this.$t("toasts.credentialReenabled"))
         if (this.currentPrompt.confirm) this.currentPrompt.confirm()
         this.closeHover()
      },
      cancel() {
         this.closeHover()
      }
   }
}
</script>