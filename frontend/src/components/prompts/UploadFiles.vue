<template>
   <div v-if="transfersCount > 0" class="upload-files" :class="{ closed: !open }">
      <div class="card floating">
         <div class="card-title">
            <div class="transfer-title">
               <h2>{{ titleText }}</h2>

               <div v-if="filesInUploadCount > 0 && filesInDownloadCount > 0" class="transfer-tabs">
                  <button
                    class="transfer-tab"
                    :class="{ active: activeView === 'uploads' }"
                    @click="activeView = 'uploads'"
                  >
                     {{ $t('transferFile.uploads') }}
                  </button>

                  <button
                    class="transfer-tab"
                    :class="{ active: activeView === 'downloads' }"
                    @click="activeView = 'downloads'"
                  >
                     {{ $t('transferFile.downloads') }}
                  </button>
               </div>
            </div>

            <div v-if="showTransferInfo" class="upload-info">
               <div class="upload-speed">{{ filesize(activeSpeed) }}/s</div>
               <div class="upload-eta">{{ formattedETA }} remaining</div>
            </div>

            <div class="action-buttons">
               <button
                 v-if="canPause"
                 :aria-label="$t('transferFile.pause')"
                 :title="$t('transferFile.pause')"
                 class="action"
                 @click="pause"
               >
                  <i class="material-icons">pause</i>
               </button>

               <button
                 v-if="canResume"
                 :aria-label="$t('transferFile.resume')"
                 :title="$t('transferFile.resume')"
                 class="action"
                 @click="resume"
               >
                  <i class="material-icons">play_arrow</i>
               </button>

               <button
                 v-if="canAbort"
                 :aria-label="$t('transferFile.abortAll')"
                 :title="$t('transferFile.abortAll')"
                 class="action"
                 @click="abortAll"
               >
                  <i class="material-icons">close</i>
               </button>

               <button
                 :aria-label="$t('transferFile.toggleUploadList')"
                 :title="$t('transferFile.toggleUploadList')"
                 class="action"
                 @click="toggle"
               >
                  <i class="material-icons">{{ open ? "keyboard_arrow_down" : "keyboard_arrow_up" }}</i>
               </button>
            </div>
         </div>

         <div v-if="activeTransfers.length" class="card-content">
            <div v-if="activeView === 'uploads'">
               <UploadFile
                 v-for="fileState in filesInUpload"
                 :key="fileState.fileObj.frontendId"
                 :aria-label="fileState.fileObj.name"
                 :data-dir="false"
                 :data-type="fileState.fileObj.name"
                 :fileState="fileState"
               />
            </div>
            <div v-else>
               <DownloadFile
                 v-for="fileState in filesInDownload"
                 :key="fileState.fileObj.id"
                 :aria-label="fileState.fileObj.name"
                 :data-dir="false"
                 :data-type="fileState.fileObj.name"
                 :fileState="fileState"
               />
            </div>
         </div>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { useTransferStore } from "@/stores/transferStore.js"
import { getUploader } from "@/transfers/upload/Uploader.js"
import UploadFile from "@/components/transfer/UploadFile.vue"
import { uploadState } from "@/transfers/upload/constants.js"
import { downloadState } from "@/transfers/downloads/constants.js"
import { getDownloader } from "@/transfers/downloads/Downloader.js"
import DownloadFile from "@/components/transfer/DownloadFile.vue"
import { filesize } from "@/utils/common.js"

export default {
   name: "TransferFiles",

   components: { DownloadFile, UploadFile },

   data() {
      return {
         open: true,
         activeView: "uploads"
      }
   },

   computed: {
      ...mapState(useTransferStore, ["upload", "download", "filesInUpload", "filesInUploadCount", "filesInDownload", "filesInDownloadCount"]),

      uploadState() {
         return uploadState
      },

      downloadState() {
         return downloadState
      },

      uploadStatus() {
         return this.upload.state
      },

      downloadStatus() {
         return this.download.state
      },

      transfersCount() {
         return this.filesInUploadCount + this.filesInDownloadCount
      },

      activeTransfers() {
         return this.activeView === "downloads" ? this.filesInDownload : this.filesInUpload
      },

      activeSpeed() {
         return this.activeView === "downloads" ? this.download.downloadSpeed : this.upload.uploadSpeed
      },

      activeEta() {
         return this.activeView === "downloads" ? this.download.eta : this.upload.eta
      },

      showTransferInfo() {
         if (this.activeView === "downloads") {
            return this.downloadStatus === downloadState.downloading
         }
         return this.uploadStatus === uploadState.uploading
      },

      canPause() {
         if (this.activeView === "downloads") {
            return this.downloadStatus === downloadState.downloading
         }
         return this.uploadStatus === uploadState.uploading
      },

      canResume() {
         if (this.activeView === "downloads") {
            return this.downloadStatus === downloadState.paused
         }
         return this.uploadStatus === uploadState.paused
      },

      canAbort() {
         if (this.activeView === "downloads") {
            return this.downloadStatus === downloadState.paused || this.downloadStatus === downloadState.downloading
         }

         return this.uploadStatus === uploadState.paused || this.uploadStatus === uploadState.uploading
      },

      titleText() {
         if (this.activeView === "downloads") {
            if (this.downloadStatus === downloadState.aborting) return this.$t("prompts.aborting")
            if (this.downloadStatus === downloadState.error) return "Downloads crashed"
            if (this.downloadState === downloadState.paused) return this.$t("prompts.pausedFilesDownload", { amount: this.filesInUploadCount })
            if (this.downloadStatus === downloadState.noInternet) return this.$t("prompts.noInternet")

            return this.$t("prompts.downloadFiles", { amount: this.filesInDownloadCount })
         }

         if (this.uploadStatus === uploadState.aborting) return this.$t("prompts.aborting")
         if (this.uploadStatus === uploadState.error) return this.$t("prompts.uploadFilesCrashed")
         if (this.uploadStatus === uploadState.uploading) return this.$t("prompts.uploadFiles", { amount: this.filesInUploadCount })
         if (this.uploadStatus === uploadState.paused) return this.$t("prompts.pausedFilesUpload", { amount: this.filesInUploadCount })
         if (this.uploadStatus === uploadState.noInternet) return this.$t("prompts.noInternet")

         return this.$t("prompts.uploadFiles", { amount: this.filesInUploadCount })
      },

      formattedETA() {
         if (!this.activeEta || this.activeEta === Infinity) {
            return "--:--:--"
         }

         let totalSeconds = this.activeEta
         const hours = Math.floor(totalSeconds / 3600)
         totalSeconds %= 3600
         const minutes = Math.floor(totalSeconds / 60)
         const seconds = Math.round(totalSeconds % 60)

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
               if (this.activeView === "downloads") {
                  getDownloader().abortAll()
               } else {
                  getUploader().abortAll()
               }
            }
         })
      },

      toggle() {
         this.open = !this.open
      },

      pause() {
         if (this.activeView === "downloads") {
            getDownloader().pauseAll()
         } else {
            getUploader().pauseAll()
         }
      },

      resume() {
         if (this.activeView === "downloads") {
            getDownloader().resumeAll()
         } else {
            getUploader().resumeAll()
         }
      }
   }
}
</script>