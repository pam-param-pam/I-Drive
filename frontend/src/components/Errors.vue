<template>
   <div>
      <template v-if="!simple">
         <div v-if="error" class="info">
            <div class="title">
               <i class="material-icons">{{ info.icon }}</i>
               <span> {{ $t(info.title) }}</span>
            </div>
            <div class="details">
               <span v-if="errorDetails"> {{ errorDetails }}</span>
            </div>
            <div>
               <a class="button button--flat">
                  <div>
                     <i class="material-icons" @click="$emit('close')">arrow_back</i>{{ $t("errors.goBack") }}
                  </div>
               </a>
            </div>
         </div>
      </template>

      <template v-else>
         <h2 class="message">
            <i class="material-icons">{{ info.icon }}</i>
            <span>{{ $t(info.title) }}</span>
            <br />
            <span v-if="errorDetails" class="details">{{ errorDetails }}</span>
         </h2>

         <button class="message error-action-button" @click="refresh">
            {{ $t("errors.tryAgain") }}
         </button>
      </template>


   </div>
</template>

<script>
import router from "@/router/index.js"
import { normalizeError } from "@/utils/common.js"

const errors = {
   0: {
      icon: "wifi_off",
      title: "errors.connection"
   },
   400: {
      icon: "error_outline",
      title: "errors.badRequest"
   },
   403: {
      icon: "error",
      title: "errors.forbidden"
   },
   404: {
      icon: "gps_off",
      title: "errors.notFound"
   },
   429: {
      icon: "block",
      title: "errors.rateLimit"
   },
   469: {
      icon: "block",
      title: "errors.folderPasswordRequired"
   },
   500: {
      icon: "error_outline",
      title: "errors.internal"
   },
   502: {
      icon: "cloud_off",
      title: "errors.badGateway"
   },
   999: {
      icon: "error_outline",
      title: "errors.clientError"
   },
   1000: {
      icon: "error_outline",
      title: "errors.unknownError"
   }
}

export default {
   name: "errors",

   props: {
      error: {
         required: true
      },
      simple: {
         type: Boolean,
         default: true
      }
   },
   emits: ["close"],

   computed: {
      normalizedError() {
         return normalizeError(this.error)
      },
      errorCode() {
         return this.normalizedError?.code
      },
      info() {
         return errors[this.errorCode] ? errors[this.errorCode] : errors[1000]
      },
      errorDetails() {
         return this.normalizedError?.details
      },
   },

   methods: {
      refresh() {
         router.go(0)
      },
   }
}
</script>
<style scoped>
.details {
  font-size: 17px !important;
  color: var(--textSecondary);
}

.error-action-button {
  margin-top: 10px;
  padding: 8px 16px;
  font-size: 14px;
  color: var(--background);
  background-color: transparent;
  border: 1px solid var(--background);
  cursor: pointer;
}

.error-action-button:hover {
  background-color: rgba(0, 123, 255, 0.1);
}

.info .button {
  margin-top: 2em;
}
</style>
