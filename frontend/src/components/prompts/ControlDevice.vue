<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t("prompts.deviceControl") }}</h2>
      </div>

      <div class="card-content">

         <!-- Device selector (only if idle) -->
         <div v-if="deviceControlStatus.status === 'idle'">
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

         <div v-if="deviceControlStatus.status !== 'idle'">
            <div v-if="deviceControlStatus.status === 'pending_master'" class="error-msg">
               <p>{{ $t("prompts.deviceControlPending") }} ({{ deviceControlStatus.status }})</p>
            </div>

            <!-- Waiting mode -->
            <div v-if="deviceControlStatus.status === 'pending_slave'" class="waiting">
               <p>{{ $t("prompts.deviceControlPending") }}({{ deviceControlStatus.status }})</p>
            </div>

            <!-- Success -->
            <div v-if="deviceControlStatus.status === 'active_master'" class="success-msg">
               <p>{{ $t("prompts.deviceControlActive") }} ({{ deviceControlStatus.status }})</p>
            </div>

            <!-- Rejected -->
            <div v-if="deviceControlStatus.status === 'active_slave'" class="error-msg">
               <p>{{ $t("prompts.deviceControlActive") }} ({{ deviceControlStatus.status }})</p>
            </div>

            <div v-if="deviceControlStatus.status === 'rejected'" class="error-msg">
               <p>{{ $t("prompts.deviceControlRejected") }} ({{ deviceControlStatus.status }})</p>
            </div>
         </div>
      </div>

      <div class="card-action">
         <button
            v-if="deviceControlStatus.status === 'pending_master'"
            :aria-label="$t('buttons.clearPending')"
            :title="$t('buttons.clearPending')"
            class="button button--flat button--red"
            @click="cancelPending"
         >
            {{ $t("buttons.clearPending") }}
         </button>
         <button
           v-if="deviceControlStatus.status === 'pending_slave'"
           :aria-label="$t('buttons.rejectPending')"
           :title="$t('buttons.rejectPending')"
           class="button button--flat button--red"
           @click="rejectPending"
         >
            {{ $t("buttons.rejectPending") }}
         </button>
         <button
           v-if="deviceControlStatus.status === 'active_master' || deviceControlStatus.status === 'active_slave'"
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
            v-if="deviceControlStatus.status === 'idle'"
            :disabled="!(deviceControlStatus.status === 'idle' && selectedDevice)"
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
      }
   },

   computed: {
      ...mapState(useMainStore, ['deviceControlStatus']),

      filteredDevices() {
         return this.devices.filter(d => d.device_id !== this.currentDeviceId)
      },

      selectedDevice() {
         return this.filteredDevices.find(d => d.device_id === this.selectedDeviceId) || null
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      requestControl() {
         if (!this.selectedDevice) return
         this.status = "pending_master"

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
