<template>
  <div>
    <h2 class="message">
      <i class="material-icons">{{ info.icon }}</i>
      <span>{{ $t(info.message, { "code": errorCode, "response": error?.response?.data }) }}</span>
    </h2>
    <button v-if="shouldRetry" @click="retry" class="message error-action-button">
      {{ $t("errors.retry") }}
    </button>
    <button v-else @click="goBack" class="message error-action-button">
      {{ $t("errors.goBack") }}
    </button>
  </div>
</template>

<script>
import router from "@/router/index.js"

const errors = {

   0: {
      icon: "cloud_off",
      message: "errors.connection"
   },
   403: {
      icon: "error",
      message: "errors.forbidden"
   },
   429: {
      icon: "block",
      message: "errors.rateLimit"
   },
   404: {
      icon: "gps_off",
      message: "errors.notFound"
   },
   469: {
      icon: "block",
      message: "errors.folderPasswordRequired"
   },
   500: {
      icon: "error_outline",
      message: "errors.internal"
   },
   1000: {
      icon: "error_outline",
      message: "errors.unknownError"
   }
}

export default {
   name: "errors",
   props: ["error"],

   computed: {
      errorCode() {
         return this.error?.response?.status
      },
      info() {
         if (this.error.code === "ERR_NETWORK") {
            return errors[0]
         }
         return errors[this.errorCode] ? errors[this.errorCode] : errors[1000]
      },
      shouldRetry() {
         return this.errorCode !== 404 && this.errorCode !== 401 && this.errorCode !== 403
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
</style>
