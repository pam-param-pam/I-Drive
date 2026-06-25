<template>
   <div
      :class="{
         'error-border': isErrorStatus || state === downloadState.error,
         'success-border': fileState.status === fileDownloadStatus.completed && state !== downloadState.noInternet,
         'warning-border': state === downloadState.paused && !isErrorStatus,
         'shake-animation': isShaking
      }"
      class="fileitem-wrapper"
   >
      <div class="fileitem-header file-icons">
         <div :aria-label="fileExtension" :data-type="fileState.fileObj.type">
            <i class="material-icons file-icon"></i>
         </div>

         <span class="file-name">{{ fileName }}</span>

         <div class="button-group">
            <button
               v-if="showTryAgainButton"
               class="action-button"
               @click="retry"
            >
               <i class="material-icons">refresh</i>
            </button>

            <button
               v-if="showDismissButton"
               class="action-button"
               @click="dismiss"
            >
               <i class="material-icons">remove</i>
            </button>
         </div>
      </div>

      <div v-if="state === downloadState.error">
         <span>
            <b class="error">{{ $t("transferFile.fatal") }}</b>
         </span>
      </div>

      <div v-else-if="state === downloadState.noInternet">
         <span>
            <b class="error">{{ $t("transferFile.noInternet") }}</b>
         </span>
      </div>

      <div v-else-if="state === downloadState.paused && !isErrorStatus">
         <span>
            <b class="warning">{{ $t("transferFile.paused") }}</b>
         </span>
      </div>

      <div v-else-if="fileState.status">
         <span v-if="fileState.status === fileDownloadStatus.queued">
            <b class="info">{{ $t("transferFile.queued") }}</b>
         </span>

         <span v-if="fileState.status === fileDownloadStatus.waitingForInternet">
            <b class="info">{{ $t("transferFile.waitingForInternet") }}</b>
         </span>

         <span v-if="fileState.status === fileDownloadStatus.retrying">
            <b class="info">{{ $t("transferFile.retrying") }}</b>
         </span>

         <span v-if="fileState.status === fileDownloadStatus.completed">
            <b class="success">{{ $t("transferFile.success") }}</b>
         </span>

         <span v-if="fileState.status === fileDownloadStatus.paused">
            <b class="warning">{{ $t("transferFile.paused") }}</b>
         </span>

         <span v-if="isErrorStatus">
            <b v-if="fileState.error" class="error">{{ fileState.error }}</b>
            <b v-else class="error">{{ $t("transferFile.failed") }}</b>
         </span>

         <div
            v-if="fileState.status === fileDownloadStatus.downloading"
            class="fileitem-progress"
         >
            <TransferProgressBar :progress="fileState.progress" />

            <span>
               <b>{{ fileState.progress }}%</b>
            </span>
         </div>
      </div>
   </div>
</template>

<script>
import { mapState } from "pinia"
import { getFileType } from "@/transfers/upload/utils/uploadHelper.js"
import TransferProgressBar from "@/components/transfer/TransferProgressBar.vue"
import { downloadFileStatus, downloadState } from "@/transfers/downloads/constants.js"
import { useTransferStore } from "@/stores/transferStore.js"
import { getDownloader } from "@/transfers/downloads/Downloader.js"

export default {
   components: { TransferProgressBar },

   props: ["fileState"],

   data() {
      return {
         isShaking: false
      }
   },

   computed: {
      ...mapState(useTransferStore, ["download"]),

      state() {
         return this.download.state
      },

      downloadState() {
         return downloadState
      },

      fileDownloadStatus() {
         return downloadFileStatus
      },

      fileName() {
         return this.fileState.fileObj.name
      },

      fileExtension() {
         return this.fileState.fileObj.extension
      },

      showTryAgainButton() {
         return this.fileState.status === downloadFileStatus.errorOccurred
      },

      showDismissButton() {
         return this.fileState.status === downloadFileStatus.failed ||
           this.fileState.status === downloadFileStatus.errorOccurred
      },
      isErrorStatus() {
         return this.fileState.status === downloadFileStatus.failed || this.fileState.status === downloadFileStatus.errorOccurred
      }
   },

   methods: {
      dismiss() {
         getDownloader().dismissFile(this.fileState.fileObj.id)
      },

      retry() {
         getDownloader().retryFile(this.fileState.fileObj.id)
      },
   }
}
</script>