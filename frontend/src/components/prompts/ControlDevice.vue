<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t("prompts.deviceControl") }}</h2>
      </div>

      <div class="card-content">
         <div v-if="!currentDeviceControlStatus.status">
            {{ $t("prompts.noWebsocketConnection") }}
         </div>

         <!-- Device selector (only if idle) -->
         <div v-else-if="currentDeviceControlStatus.status === 'idle'">
            <div v-if="filteredDevices.length === 0" class="empty-msg">
               {{ $t("prompts.noOtherDevices") }}
            </div>

            <div v-else>
               <select
                  v-model="selectedDeviceId"
                  class="input input--block styled-select"
               >
                  <option value="">
                     {{ $t("prompts.selectDevice") }}
                  </option>

                  <option
                     v-for="dev in filteredDevices"
                     :key="dev.device_id"
                     :value="dev.device_id"
                  >
                     {{ dev.device_name }} ({{ dev.device_id }})
                  </option>
               </select>
            </div>
         </div>

         <!-- STATUS PANEL -->
         <div v-if="currentDeviceControlStatus.status && currentDeviceControlStatus.status !== 'idle'" class="status-panel">
            <div
               :class="[
                  'status-box',
                  statusClassMap[currentDeviceControlStatus.status] || 'status-neutral'
                ]"
            >
               <i
                 class="material-icons status-icon"
                 :class="{ 'hourglass-flip': currentDeviceControlStatus.status === 'pending_master'}"
               >
                  {{ statusIconMap[currentDeviceControlStatus.status] || "info" }}
               </i>

               <div class="status-text">
                  <p class="status-title">
                     {{ statusTitleMap[currentDeviceControlStatus.status] }}
                  </p>
                  <p class="status-code">({{ currentDeviceControlStatus.status }})</p>
               </div>
            </div>

         </div>
      </div>

      <div class="card-action">
         <button
            v-if="currentDeviceControlStatus.status === 'pending_master'"
            :aria-label="$t('buttons.clearPending')"
            :title="$t('buttons.clearPending')"
            class="button button--flat button--red"
            @click="cancelPending"
         >
            {{ $t("buttons.clearPending") }}
         </button>
         <button
            v-if="currentDeviceControlStatus.status === 'active_master' || currentDeviceControlStatus.status === 'active_slave'"
            :aria-label="$t('buttons.clearActive')"
            :title="$t('buttons.clearActive')"
            class="button button--flat button--red"
            @click="clearActive"
         >
            {{ $t("buttons.clearActive") }}
         </button>
         <button
            :aria-label="$t('buttons.ok')"
            :title="$t('buttons.ok')"
            class="button button--flat button--grey"
            @click="close"
         >
            {{ $t("buttons.ok") }}
         </button>
         <button
            v-if="currentDeviceControlStatus.status === 'idle' && filteredDevices.length > 0"
            :disabled="!(currentDeviceControlStatus.status === 'idle' && selectedDevice)"
            class="button button--flat"
            @click="requestControl"
         >
            {{ $t("buttons.control") }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "ControlDevice",

   props: {
      devices: { type: Array, required: true },
      currentDeviceId: { type: String, required: true }
   },

   data() {
      return {
         selectedDeviceId: "",
         _tickInterval: null,
         nowTick: null
      }
   },
   created() {
      this.fetchStatus()
      this._tickInterval = setInterval(() => {
         this.nowTick = Date.now()
      }, 500)
   },
   beforeUnmount() {
      clearInterval(this._tickInterval)
   },
   computed: {
      ...mapState(useMainStore, ["deviceControlStatus"]),
      currentDeviceControlStatus() {
         const _ = this.nowTick

         let st = this.deviceControlStatus
         if (!st) return { status: "unknown" }

         if (!st.expiry) return st

         const now = this.nowTick
         let expiryMs = Number(st.expiry) * 1000

         if (now >= expiryMs) this.fetchStatus()

         return st
      },
      filteredDevices() {
         return this.devices.filter(d => d.device_id !== this.currentDeviceId)
      },

      selectedDevice() {
         return this.filteredDevices.find(d => d.device_id === this.selectedDeviceId) || null
      },

      statusTitleMap() {
         return {
            pending_master: this.$t("prompts.deviceControlPending"),
            active_master: this.$t("prompts.deviceControlActive"),
            active_slave: this.$t("prompts.deviceControlActive"),
            rejected_master: this.$t("prompts.deviceControlRejected")
         }
      },

      statusIconMap() {
         return {
            pending_master: "hourglass_empty",
            active_master: "check_circle",
            active_slave: "check_circle",
            rejected_master: "cancel",
         }
      },

      statusClassMap() {
         return {
            pending_master: "status-waiting",
            active_master: "status-success",
            active_slave: "status-success",
            rejected_master: "status-error",
            unknown: "status-error",
            expired: "status-error"
         }
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),
      fetchStatus() {
         this.$socket.send(JSON.stringify({ op_code: 16}))
      },
      requestControl() {
         if (!this.selectedDevice) return
         this.$socket.send(JSON.stringify({ op_code: 13, message: { device_id: this.selectedDevice.device_id } }))
      },
      cancelPending() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": {"type": "cancel"}}))
      },
      clearActive() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": {"type": "clear"}}))
      },
      rejectPending() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": {"type": "reject"}}))
      },
      close() {
         this.closeHover()
      }
   }

}
</script>
<style>
.status-panel {
 margin-top: 1rem;
}

.status-box {
 display: flex;
 align-items: center;
 padding: 1rem;
 border-radius: 8px;
 border: 1px solid var(--divider);
 gap: 1rem;
}

.status-icon {
 font-size: 28px !important;
}

.status-text .status-title {
 font-weight: 600;
 margin: 0;
}

.status-text .status-code {
 margin: 0.3rem 0 0 0;
 font-size: 13px;
 color: var(--textSecondary);
}

.status-waiting {
 background: var(--surfaceSecondary);
}

.status-success {
 background: rgba(40, 167, 69, 0.15);
 border-color: rgba(40, 167, 69, 0.4);
 color: var(--textPrimary);
}

.status-error {
 background: rgba(220, 53, 69, 0.15);
 border-color: rgba(220, 53, 69, 0.4);
 color: var(--textPrimary);
}

.status-neutral {
 background: var(--surfacePrimary);
}
.hourglass-flip {
   display: inline-block;
   animation: hourglassFlip 4s ease-in-out infinite;
   transform-origin: center;
}

@keyframes hourglassFlip {
   0% {
      transform: rotate(0deg);
   }
   10% {
      transform: rotate(180deg);
   }
   45% {
      transform: rotate(180deg);
   }
   55% {
      transform: rotate(0deg);
   }
   100% {
      transform: rotate(0deg);
   }
}
</style>