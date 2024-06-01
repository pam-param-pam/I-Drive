<template>
  <div>
    <header-bar v-if="showHeader" showMenu showLogo />

    <h2 class="message">
      <i class="material-icons">{{ info.icon }}</i>
      <span>{{ $t(info.message) }}</span>
    </h2>
  </div>
</template>

<script>
import HeaderBar from "@/components/header/HeaderBar.vue"

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
}

export default {
  name: "errors",
  components: {
    HeaderBar,
  },
  props: ["errorCode", "showHeader"],
  methods: {
  },

  computed: {
    info() {
      return errors[this.errorCode] ? errors[this.errorCode] : errors[500]
    },
  },
}
</script>
