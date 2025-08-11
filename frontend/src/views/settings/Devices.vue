<template>
  <errors v-if="error" :error="error" />
  <div v-else-if="!loading" class="row">
    <div class="column" style="width: 100%; margin-top: 2rem;">
      <div class="card">
        <div class="card-title">
          <h2>{{ $t("settings.devices") }}</h2>
        </div>

        <div class="card-content">
          <table class="devices-table" v-if="devices.length > 0">
            <thead>
            <tr>
              <th class="share-name-column icon-column"></th>
              <th class="share-name-column">{{ $t("settings.deviceName") }}</th>
              <th class="share-name-column">{{ $t("settings.country") }}</th>
              <th class="share-name-column">{{ $t("settings.city") }}</th>
              <th class="share-name-column">{{ $t("settings.expiresAt") }}</th>
              <th class="share-name-column">{{ $t("settings.lastUsedAt") }}</th>
            </tr>
            </thead>
            <tbody>
            <tr v-for="device in devices" :key="device.device_id">
              <td>
                <i v-if="device.device_type === 'pc'" class="material-icons">desktop_windows</i>
                <i v-else-if="device.device_type === 'mobile'" class="material-icons">tablet</i>
                <i v-else-if="device.device_type === 'code'" class="material-icons">terminal</i>
              </td>
              <td>{{ device.device_name }}</td>
              <td>{{ device.country || "-" }}</td>
              <td>{{ device.city || "-" }}</td>
              <td>{{ humanTime(device.expires_at) || "-" }}</td>
              <td>{{ humanTime(device.last_used_at) || "-" }}</td>
              <td>
                <button @click="revokeADevice(device.device_id)" :disabled="device.device_id === localDeviceId" class="button button--flat button--small">
                  {{ $t("buttons.revoke") }}
                </button>
              </td>
            </tr>
            </tbody>
          </table>
        </div>

        <div class="card-action">
          <button @click="logoutAll" class="button button--danger button--flat button--red">
            {{ $t("buttons.logoutAllDevices") }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import dayjs from "@/utils/dayjsSetup.js"
import { getActiveDevices, logoutAllDevices, revokeDevice } from "@/api/user.js"
import { forceLogout } from "@/utils/auth.js"
import Errors from "@/components/Errors.vue"

export default {
   name: "Devices",
   components: { Errors },
   data() {
      return {
         devices: []
      }
   },
   computed: {
      ...mapState(useMainStore, ["loading", "error"]),
      localDeviceId() {
         return localStorage.getItem("device_id")
      }
   },
   async created() {
      this.setLoading(true)
      try {
         this.devices = await getActiveDevices()
      } catch (error) {
         console.error(error)
         this.setError(error)
      } finally {
         this.setLoading(false)
      }
   },
   methods: {
      ...mapActions(useMainStore, ["setLoading", "setError"]),
      humanTime(date) {
         if (!date) return null
         if (this.settings?.dateFormat) {
            return dayjs(date, "YYYY-MM-DD HH:mm").format("DD/MM/YYYY, hh:mm")
         }

         return dayjs(date, "YYYY-MM-DD HH:mm").fromNow()
      },
      async revokeADevice(deviceId) {
         await revokeDevice(deviceId)
         this.devices = this.devices.filter(d => d.device_id !== deviceId)
         this.$toast.success(this.$t("toasts.deviceRevoked"))
      },
      async logoutAll() {
         await logoutAllDevices()
         await forceLogout()
      }
   }
}
</script>

<style scoped>
table th, table td {
 padding-right: 10px;
 white-space: nowrap;
}
</style>