<template>
  <div>
    <h2 class="message">
      <i class="material-icons">{{ info.icon }}</i>
      <span>{{ $t(info.message, {"code": errorCode, "response": error.response.data}) }}</span>
    </h2>
  </div>
</template>

<script>
const errors = {

   0: {
      icon: "cloud_off",
      message: "errors.connection",
   },
   403: {
      icon: "error",
      message: "errors.forbidden",
   },
   429: {
      icon: "block",
      message: "errors.rateLimit",
   },
   404: {
      icon: "gps_off",
      message: "errors.notFound",
   },
   469: {
      icon: "block",
      message: "errors.folderPasswordRequired",
   },
   500: {
      icon: "error_outline",
      message: "errors.internal",
   },
   1000: {
      icon: "error_outline",
      message: "errors.unknownError",
   },
}

export default {
   name: "errors",
   props: ["error"],
   methods: {},

   computed: {
      errorCode() {
        return this.error?.response.status
      },
      info() {
         return errors[this.errorCode] ? errors[this.errorCode] : errors[1000]
      },
   },
}
</script>
