<template>
  <div
    v-if="filesInUploadCount > 0"
    class="upload-files"
    v-bind:class="{ closed: !open }"
  >
    <div class="card floating">
      <div class="card-title">
        <h2>{{ $t("prompts.uploadFiles", {amount: filesInUploadCount}) }}</h2>
        <div class="upload-info">
          <div class="upload-speed">{{ filesize(uploadSpeed)}}/s</div>
          <div class="upload-eta">{{ formattedETA }} remaining</div>
        </div>
        <button
          class="action"
          @click="abort()"
          :aria-label="$t('uploadFile.abortAll')"
          :title="$t('uploadFile.abortAll')"
        >
          <i class="material-icons">{{ "cancel" }}</i>
        </button>
        <button
          class="action"
          @click="toggle()"
          :aria-label="$t('uploadFile.toggleUploadList')"
          :title="$t('uploadFile.toggleUploadList')"
        >
          <i class="material-icons">{{
              open ? "keyboard_arrow_down" : "keyboard_arrow_up"
            }}</i>
        </button>
      </div>
      <div class="card-content">
        <UploadFile
          v-for="file in filesInUpload"
          :key="file.frontedId"
          :file="file"
          :data-dir="false"
          :data-type="file.type"
          :aria-label="file.name"
        />
      </div>
    </div>
  </div>
</template>

<script>
import UploadFile from "@/components/UploadFile.vue"
import {mapActions, mapState} from "pinia"
import {useUploadStore} from "@/stores/uploadStore.js"
import {filesize} from "@/utils/index.js"

export default {
   name: "uploadFiles",
   components: {UploadFile},
   data() {
      return {
         open: true,
      }
   },
   computed: {
      ...mapState(useUploadStore, ["filesInUpload", "filesInUploadCount", "uploadSpeed", "eta"]),
      formattedETA() {
         if (!this.eta || this.eta === Infinity) {
            return "--:--:--"
         }

         let totalSeconds = this.eta
         const hours = Math.floor(totalSeconds / 3600)
         totalSeconds %= 3600
         const minutes = Math.floor(totalSeconds / 60)
         const seconds = Math.round(totalSeconds % 60)

         return `${hours.toString().padStart(2, "0")}:${minutes
            .toString()
            .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`
      },
   },
   methods: {
      ...mapActions(useUploadStore, ["abortAll"]),

      filesize,

      toggle() {
         this.open = !this.open
      },
      abort() {
         this.$toast.info(this.$t("toasts.aborting"))
      }

   },
}
</script>
