<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.scanQR") }}</h2>
    </div>

    <div class="card-content">
      <p v-if="!deviceInfo">{{ $t("settings.qrCodeWarning") }}</p>
      <p v-else>{{ $t("settings.qrDeviceInfo") }}</p>

      <!-- QR Code Scanner -->
      <qrcode-stream
        v-if="!deviceInfo"
        @detect="onDetect"
        @error="onError"
        :track="paintBoundingBox"
        class="qr-scanner"
      />
      <p v-if="error" class="text-error">{{ error }}</p>

      <!-- Device info preview -->
      <div v-if="deviceInfo" class="device-info">
        <p><b>Device Name:</b> {{ deviceInfo.device_name }}</p>
        <p><b>Device ID:</b> {{ deviceInfo.device_id }}</p>
        <p><b>IP Address:</b> {{ deviceInfo.ip_address }}</p>
        <p><b>User Agent:</b> {{ deviceInfo.user_agent }}</p>
        <p v-if="deviceInfo.country"><b>Country:</b> {{ deviceInfo.country }}</p>
        <p v-if="deviceInfo.city"><b>City:</b> {{ deviceInfo.city }}</p>

        <p>
          <b>Device Type:</b> {{ "&#8205;" }}
          <i v-if="deviceInfo.device_type === 'pc'" class="material-icons">desktop_windows</i>
          <i v-else-if="deviceInfo.device_type === 'mobile'" class="material-icons">tablet</i>
          <i v-else-if="deviceInfo.device_type === 'code'" class="material-icons">terminal</i>
          {{ deviceInfo.device_type }}
        </p>
      </div>

      <p v-if="fetching">Fetching device info...</p>
      <p v-if="fetchError" class="text-error">{{ fetchError }}</p>
    </div>

    <div class="card-action">
      <button
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
        class="button button--flat button--grey"
        @click="cancel"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        :disabled="!deviceInfo || !canApprove"
        :aria-label="$t('buttons.confirm')"
        :title="$t('buttons.confirm')"
        class="button button--flat"
        @click="confirm"
      >
        <!-- Show countdown if user must wait -->
        <span v-if="deviceInfo && !canApprove">
    {{ $t("buttons.confirm") }} ({{ countdown }}s)
  </span>
        <span v-else>
    {{ $t("buttons.confirm") }}
  </span>
      </button>
    </div>
  </div>
</template>

<script>
import { QrcodeStream } from "vue-qrcode-reader"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { approveQrSession, closePendingQrSession, getQrSessionDeviceInfo } from "@/api/user.js"

export default {
   name: "scan-qr-prompt",
   components: { QrcodeStream },

   data() {
      return {
         decodedValue: null,
         error: null,
         fetchError: null,
         fetching: false,
         sessionId: null,
         deviceInfo: null,
         countdown: 0,
         canApprove: false
      }
   },

   computed: {
      ...mapState(useMainStore, ["currentPrompt"])
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      paintBoundingBox(detectedCodes, ctx) {
         for (const detectedCode of detectedCodes) {
            const { boundingBox: { x, y, width, height } } = detectedCode
            ctx.lineWidth = 2
            ctx.strokeStyle = "#007bff"
            ctx.strokeRect(x, y, width, height)
         }
      },

      async onDetect(detectedCodes) {
         const qrData = detectedCodes[0]?.rawValue
         if (!qrData) {
            this.error = "No QR code detected"
            return
         }

         this.decodedValue = qrData
         this.error = null
         this.deviceInfo = null
         this.fetchError = null
         this.fetching = true
         this.canApprove = false

         try {
            const url = new URL(qrData)
            const pathParts = url.pathname.split("/")
            this.sessionId = pathParts[pathParts.length - 1]

            const data = await getQrSessionDeviceInfo(this.sessionId)
            this.deviceInfo = {
               device_name: data.device_name,
               device_id: data.device_id,
               ip_address: data.ip,
               user_agent: data.user_agent,
               country: data.country,
               city: data.city,
               device_type: data.device_type
            }

            // Start 3-second countdown
            this.countdown = 2
            const interval = setInterval(() => {
               this.countdown--
               if (this.countdown <= 0) {
                  clearInterval(interval)
                  this.canApprove = true
               }
            }, 1000)

         } catch (err) {
            console.error(err)
            this.fetchError = "Invalid QR code or session"
         } finally {
            this.fetching = false
         }
      },

      onError(err) {
         this.error = `[${err.name}]: `
         if (err.name === "NotAllowedError") {
            this.error += "you need to grant camera access permission"
         } else if (err.name === "NotFoundError") {
            this.error += "no camera on this device"
         } else if (err.name === "NotSupportedError") {
            this.error += "secure context required (HTTPS or localhost)"
         } else if (err.name === "NotReadableError") {
            this.error += "is the camera already in use?"
         } else {
            this.error += err.message
         }
      },

      async confirm() {
         if (!this.sessionId) return
         await approveQrSession(this.sessionId)
         this.$toast.success(this.$t("toasts.qrSessionApproved"))
         this.closeHover()
      },
      async cancel() {
         console.log("CANCEL")
         console.log(this.sessionId)
         try {
            if (this.sessionId) await closePendingQrSession(this.sessionId)
         } catch (e) {}
         this.closeHover()
      }
   }
}
</script>

<style scoped>
.qr-scanner {
 width: 100%;
 max-width: 400px;
 height: 300px;
 margin: 1rem auto;
 border: 2px solid #007bff;
 border-radius: 12px;
 overflow: hidden;
 position: relative;
}

.text-error {
 color: red;
 margin-top: 0.5rem;
 text-align: center;
}

.device-info {
 border: 1px solid #ccc;
 padding: 0.5rem;
 margin-top: 1rem;
 border-radius: 8px;
}

.device-info p {
 margin: 0.25rem 0;
}

.material-icons {
 font-size: 20px !important;
 vertical-align: -5px; /* moves it lower */
}
</style>
