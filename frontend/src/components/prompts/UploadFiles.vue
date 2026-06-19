<template>
   <div v-if="transfersCount > 0" class="upload-files" v-bind:class="{ closed: !open }">
      <div class="card floating">
         <div class="card-title">
            <div class="transfer-title">
               <h2>{{ titleText }}</h2>

               <div v-if="true" class="transfer-tabs">
                  <button
                    class="transfer-tab"
                    :class="{ active: activeView === 'uploads' }"
                    @click="activeView = 'uploads'"
                  >
                     Uploads
                  </button>

                  <button
                    class="transfer-tab"
                    :class="{ active: activeView === 'downloads' }"
                    @click="activeView = 'downloads'"
                  >
                     Downloads
                  </button>
               </div>
            </div>

            <div v-if="showTransferInfo" class="upload-info">
               <div class="upload-speed">{{ filesize(activeSpeed) }}/s</div>
               <div class="upload-eta">{{ formattedETA }} remaining</div>
            </div>

            <div class="action-buttons">
               <button
                 v-if="activeView === 'uploads' && state === uploadState.uploading"
                 :aria-label="$t('uploadFile.pause')"
                 :title="$t('uploadFile.pause')"
                 class="action"
                 @click="pause"
               >
                  <i class="material-icons">pause</i>
               </button>

               <button
                 v-if="activeView === 'uploads' && state === uploadState.paused"
                 :aria-label="$t('uploadFile.pause')"
                 :title="$t('uploadFile.pause')"
                 class="action"
                 @click="resume"
               >
                  <i class="material-icons">play_arrow</i>
               </button>

               <button
                 v-if="activeView === 'uploads' && state === uploadState.paused"
                 :aria-label="$t('uploadFile.abortAll')"
                 :title="$t('uploadFile.abortAll')"
                 class="action"
                 @click="abortAll"
               >
                  <i class="material-icons">close</i>
               </button>

               <button
                 :aria-label="$t('uploadFile.toggleUploadList')"
                 :title="$t('uploadFile.toggleUploadList')"
                 class="action"
                 @click="toggle"
               >
                  <i class="material-icons">{{ open ? "keyboard_arrow_down" : "keyboard_arrow_up" }}</i>
               </button>
            </div>
         </div>

         <div v-if="activeTransfers?.length" class="card-content">
            <UploadFile
              v-if="activeView === 'uploads'"
              v-for="fileState in filesInUpload"
              :key="fileState.fileObj.frontendId"
              :aria-label="fileState.fileObj.name"
              :data-dir="false"
              :data-type="fileState.fileObj.name"
              :fileState="fileState"
            />

            <DownloadFile
              v-if="activeView === 'downloads'"
              v-for="fileState in filesInDownload"
              :key="fileState.fileObj.frontendId"
              :aria-label="fileState.fileObj.name"
              :data-dir="false"
              :data-type="fileState.fileObj.name"
              :fileState="fileState"
            />
         </div>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useUploadStore } from "@/stores/uploadStore.js"
import { useDownloadStore } from "@/stores/downloadStore.js"
import { filesize } from "@/utils/index.js"
import upload from "@/components/prompts/Upload.vue"
import { uploadState } from "@/utils/constants.js"
import { useMainStore } from "@/stores/mainStore.js"
import { getUploader } from "@/transfers/upload/Uploader.js"
import DownloadFile from "@/components/transfer/DownloadFile.vue"
import UploadFile from "@/components/transfer/UploadFile.vue"

export default {
   name: "uploadFiles",

   components: { UploadFile, DownloadFile },

   data() {
      return {
         open: true,
         activeView: "uploads"
      }
   },

   computed: {
      ...mapState(useUploadStore, ["filesInUpload", "filesInUploadCount", "uploadSpeed", "eta", "state"]),
      ...mapState(useDownloadStore, ["filesInDownload", "filesInDownloadCount", "downloadSpeed", "downloadEta", "downloadState"]),

      uploadState() {
         return uploadState
      },

      upload() {
         return upload
      },

      transfersCount() {
         return this.filesInUploadCount + this.filesInDownloadCount
      },

      activeTransfers() {
         return this.activeView === "downloads" ? this.filesInDownload : this.filesInUpload
      },

      activeCount() {
         return this.activeView === "downloads" ? this.filesInDownloadCount : this.filesInUploadCount
      },

      activeSpeed() {
         return this.activeView === "downloads" ? this.downloadSpeed : this.uploadSpeed
      },

      activeEta() {
         return this.activeView === "downloads" ? this.downloadEta : this.eta
      },

      showTransferInfo() {
         if (this.activeView === "downloads") {
            return this.filesInDownloadCount > 0
         }

         return this.state === uploadState.uploading
      },

      titleText() {
         if (this.activeView === "downloads") {
            return `Downloading ${this.activeCount} ${this.activeCount === 1 ? "file" : "files"}`
         }
         if (this.state === uploadState.aborting) {
            return this.$t("prompts.aborting")
         }

         if (this.state === uploadState.error) {
            return this.$t("prompts.uploadFilesCrashed")
         }

         if (this.state === uploadState.uploading) {
            return this.$t("prompts.uploadFiles", { amount: this.filesInUploadCount })
         }

         if (this.state === uploadState.paused) {
            return this.$t("prompts.pausedFilesUpload", { amount: this.filesInUploadCount })
         }

         if (this.state === uploadState.noInternet) {
            return this.$t("prompts.noInternet")
         }

         return this.$t("prompts.uploadFiles", { amount: this.filesInUploadCount })
      },

      formattedETA() {
         if (!this.activeEta || this.activeEta === Infinity) {
            return "--:--:--"
         }

         let totalSeconds = this.activeEta
         let hours = Math.floor(totalSeconds / 3600)
         totalSeconds %= 3600
         let minutes = Math.floor(totalSeconds / 60)
         let seconds = Math.round(totalSeconds % 60)

         return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`
      }
   },

   watch: {
      filesInUploadCount() {
         this.ensureValidActiveView()
      },

      filesInDownloadCount() {
         this.ensureValidActiveView()
      }
   },

   mounted() {
      this.ensureValidActiveView()
   },

   methods: {
      ...mapActions(useMainStore, ["showHover"]),

      filesize,

      ensureValidActiveView() {
         if (this.activeView === "uploads" && this.filesInUploadCount === 0 && this.filesInDownloadCount > 0) {
            this.activeView = "downloads"
         }

         if (this.activeView === "downloads" && this.filesInDownloadCount === 0 && this.filesInUploadCount > 0) {
            this.activeView = "uploads"
         }
      },

      async abortAll() {
         this.showHover({
            prompt: "AbortAllWarning",
            confirm: () => {
               getUploader().abortAll()
            }
         })
      },

      toggle() {
         this.open = !this.open
      },

      pause() {
         getUploader().pauseAll()
      },

      resume() {
         getUploader().resumeAll()
      }
   }
}
</script>