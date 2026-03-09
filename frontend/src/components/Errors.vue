<template>
   <div>
      <template v-if="!simple">
         <div v-if="error" class="info">
            <div class="title">
               <i class="material-icons">{{ info.icon }}</i>
               <span> {{ $t(info.message) }}</span>
            </div>
            <div class="details">
               <span v-if="errorDetails"> {{ errorDetails}}</span>
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
            <span>{{ $t(info.message, { code: errorCode, response: error?.response?.data }) }}</span>
            <br />
            <span v-if="errorDetails" class="details">{{ errorDetails }}</span>
         </h2>
         <!-- buttons always rendered -->
         <button v-if="shouldRetry" class="message error-action-button" @click="retry">
            {{ $t("errors.retry") }}
         </button>

         <button v-else class="message error-action-button" @click="goBack">
            {{ $t("errors.goBack") }}
         </button>
      </template>



   </div>
</template>

<script>
import router from "@/router/index.js"

const errors = {
   0: {
      icon: "wifi_off",
      message: "errors.connection"
   },
   400: {
      icon: "error_outline",
      message: "errors.badRequest"
   },
   403: {
      icon: "error",
      message: "errors.forbidden"
   },
   404: {
      icon: "gps_off",
      message: "errors.notFound"
   },
   429: {
      icon: "block",
      message: "errors.rateLimit"
   },
   469: {
      icon: "block",
      message: "errors.folderPasswordRequired"
   },
   500: {
      icon: "error_outline",
      message: "errors.internal"
   },
   502: {
      icon: "cloud_off",
      message: "errors.badGateway"
   },
   1000: {
      icon: "error_outline",
      message: "errors.unknownError"
   }
}

export default {
   name: "errors",

   props: {
      error: Object,
      simple: {
         type: Boolean,
         default: true
      }
   },
   emits: ['close'],

   computed: {
      errorCode() {
         return this.error?.status
      },
      info() {
         if (this.error.code === "ERR_NETWORK") {
            return errors[0]
         }
         return errors[this.errorCode] ? errors[this.errorCode] : errors[1000]
      },
      shouldRetry() {
         return this.errorCode !== 404 && this.errorCode !== 401 && this.errorCode !== 403
      },
      errorDetails() {
         return this.error?.response?.data?.details
      }
   },

   methods: {
      retry() {
         router.go(0)
      },

      goBack() {
         router.go(-1)
      }
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
