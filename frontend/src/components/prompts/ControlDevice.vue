<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t("prompts.deviceControl") }}</h2>
      </div>

      <div v-if="!isControlExpanded" class="card-content">
         <!-- Device selector (only if idle) -->
         <div v-if="currentDeviceControlStatus.status === 'idle'">
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
                  <p v-if="roleTitle" class="status-code">
                     {{ $t("prompts.deviceControlRole") }}:
                     <strong>{{ roleTitle }}</strong>
                  </p>
                  <div v-if="peerInfo">
                     <p class="status-code">
                        {{ $t("prompts.peerDevice") }}:
                        <strong>{{ peerInfo.device_name }}</strong>
                        ({{ peerInfo.device_id }})
                     </p>
                  </div>
               </div>
            </div>
         </div>
      </div>

      <div>
         <!-- EXPANDABLE DEVICE CONTROL SECTION -->
         <div v-if="currentDeviceControlStatus.status === 'active_master'" class="expandable-section card-content">
            <div class="expandable-header" @click="isControlExpanded = !isControlExpanded">
               <strong>{{ $t("prompts.controlOptions") }}</strong>
               <i class="material-icons expand-icon" :class="{ expanded: isControlExpanded }">
                  keyboard_arrow_down
               </i>
            </div>

            <div v-if="isControlExpanded" class="expandable-content">
               <p>
                  <label>
                     <input v-model="deviceControlOptions.isDeviceControlActive" type="checkbox" />
                     {{ $t("prompts.isDeviceControlActive") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="deviceControlOptions.isNavigationActive" type="checkbox" />
                     {{ $t("prompts.isNavigationActive") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="deviceControlOptions.isVideoToggleActive" type="checkbox" />
                     {{ $t("prompts.isVideoToggleActive") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="deviceControlOptions.isVideoSeekActive" type="checkbox" />
                     {{ $t("prompts.isVideoSeekActive") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="deviceControlOptions.isVideoSubtitlesActive" type="checkbox" />
                     {{ $t("prompts.isVideoSubtitlesActive") }}
                  </label>
               </p>
               <p>
                  <label>
                     <input v-model="deviceControlOptions.isVideoFullscreenActive" type="checkbox" />
                     {{ $t("prompts.isVideoFullscreenActive") }}
                  </label>
               </p>
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
            :aria-label="$t('buttons.stopActive')"
            :title="$t('buttons.stopActive')"
            class="button button--flat button--red"
            @click="stopActive"
         >
            {{ $t("buttons.stopActive") }}
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
import { getActiveDevices } from "@/api/user.js"

export default {
   name: "ControlDevice",

   data() {
      return {
         devices: [],
         selectedDeviceId: "",
         _tickInterval: null,
         nowTick: null,
         isControlExpanded: false,
      }
   },
   created() {
      this.fetchStatus()
      this.fetchDevices()
      this._tickInterval = setInterval(() => {
         this.nowTick = Date.now()
      }, 500)
   },
   beforeUnmount() {
      clearInterval(this._tickInterval)
   },
   computed: {
      ...mapState(useMainStore, ["deviceControlStatus", "deviceId", "deviceControlOptions"]),
      peerInfo() {
         const st = this.currentDeviceControlStatus
         if (!st || !st.peer) return null

         const peerId = st.peer

         const peer = this.devices.find(d => d.device_id === peerId)
         return peer
            ? { device_id: peer.device_id, device_name: peer.device_name }
            : { device_id: peerId, device_name: "Unknown" }
      },

      roleTitle() {
         const s = this.currentDeviceControlStatus.status
         if (s === "active_master") return this.$t("prompts.roleMaster")
         if (s === "active_slave") return this.$t("prompts.roleSlave")
         if (s === "pending_master") return this.$t("prompts.roleMasterPending")
         if (s === "pending_slave") return this.$t("prompts.roleSlavePending")
         if (s === "rejected_master") return this.$t("prompts.rejectedMaster")
         return null
      },
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
         console.log(this.deviceId)
         return this.devices.filter(d => d.device_id !== this.deviceId)
      },

      selectedDevice() {
         return this.filteredDevices.find(d => d.device_id === this.selectedDeviceId) || null
      },

      statusTitleMap() {
         return {
            pending_master: this.$t("prompts.deviceControlPending"),
            active_master: this.$t("prompts.deviceControlActive"),
            active_slave: this.$t("prompts.deviceControlActive"),
            rejected_master: this.$t("prompts.deviceControlRejected"),
            unknown: this.$t("prompts.deviceControlUnknown")
         }
      },

      statusIconMap() {
         return {
            pending_master: "hourglass_empty",
            active_master: "check_circle",
            active_slave: "check_circle",
            rejected_master: "cancel",
            unknown: "dangerous"
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
      async fetchDevices() {
         this.devices = await getActiveDevices()
      },
      fetchStatus() {
         this.$socket.send(JSON.stringify({ op_code: 16 }))
      },
      requestControl() {
         if (!this.selectedDevice) return
         this.$socket.send(JSON.stringify({ op_code: 13, message: { device_id: this.selectedDevice.device_id } }))
      },
      cancelPending() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": { "type": "cancel" } }))
      },
      stopActive() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": { "type": "stop" } }))
      },
      rejectPending() {
         this.$socket.send(JSON.stringify({ op_code: 14, "message": { "type": "reject" } }))
      },
      close() {
         this.closeHover()
      }
   }

}
</script>
<style>
.card.floating {
 max-width: 26em !important;
}

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
 padding-bottom: 0.3em;
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

.role-peer-info {
 margin-top: 0.8rem;
 padding-left: 0.3rem;
}

.role-peer-info .role-line {
 margin: 0 0 0.3rem 0;
}

.role-peer-info .peer-line {
 margin: 0;
 color: var(--textSecondary);
}

</style>