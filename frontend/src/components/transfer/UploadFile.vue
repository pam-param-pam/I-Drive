<template>
   <div
     :class="{
         'error-border': isErrorStatus(fileState.status) || state === uploadState.error,
         'success-border': (fileState.status === fileUploadStatus.uploaded || fileState.status === fileUploadStatus.waitingForSave) && state !== uploadState.noInternet,
         'warning-border': state === uploadState.paused && !isErrorStatus(fileState.status),
         'shake-animation': isShaking
      }"
     class="fileitem-wrapper"
   >
      <div class="fileitem-header file-icons">
         <div :aria-label="fileState.fileObj.extension" :data-type="getFileType(fileState.fileObj.name)">
            <i class="material-icons file-icon"></i>
         </div>

         <span class="file-name">{{ fileState.fileObj.name }}</span>

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

      <div v-if="state === uploadState.error">
         <span>
            <b class="error">{{ $t("transferFile.fatal") }}</b>
         </span>
      </div>

      <div v-else-if="state === uploadState.noInternet">
         <span>
            <b class="error">{{ $t("transferFile.noInternet") }}</b>
         </span>
      </div>

      <div v-else-if="state === uploadState.paused && !isErrorStatus(fileState.status)">
         <span>
            <b class="warning">{{ $t("transferFile.paused") }}</b>
         </span>
      </div>

      <div v-else-if="fileState.status">
         <span v-if="fileState.status === fileUploadStatus.preparing">
            <b class="info">{{ $t("transferFile.preparing") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.waitingForInternet">
            <b class="info">{{ $t("transferFile.waitingForInternet") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.retrying">
            <b class="info">{{ $t("transferFile.retrying") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.uploaded">
            <b class="success">{{ $t("transferFile.success") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.waitingForSave">
            <b class="success">{{ $t("transferFile.waitingForSave") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.paused">
            <b class="warning">{{ $t("transferFile.paused") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.saveFailed">
            <b v-if="fileState.error" class="error">{{ fileState.error.details }}</b>
            <b v-else class="error">{{ $t("transferFile.saveFailed") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.uploadFailed">
            <b v-if="fileState.error" class="error">{{ fileState.error }}</b>
            <b v-else class="error">{{ $t("transferFile.uploadFailed") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.errorOccurred">
            <b v-if="fileState.error" class="error">{{ fileState.error }}</b>
            <b v-else class="error">{{ $t("transferFile.failed") }}</b>
         </span>

         <span v-if="fileState.status === fileUploadStatus.fileGoneInRequestProducer || fileState.status === fileUploadStatus.fileGoneInUpload">
            <b class="error">{{ $t("transferFile.fileGone") }}</b>
         </span>

         <div
           v-if="fileState.status === fileUploadStatus.uploading"
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
import { getFileType, isErrorStatus } from "@/transfers/upload/utils/uploadHelper.js"
import { getUploader } from "@/transfers/upload/Uploader.js"
import TransferProgressBar from "@/components/transfer/TransferProgressBar.vue"
import { uploadFileStatus, uploadState } from "@/transfers/upload/constants.js"
import { useTransferStore } from "@/stores/transferStore.js"

export default {
   components: { TransferProgressBar },

   props: ["fileState"],

   data() {
      return {
         isPaused: false,
         isShaking: false
      }
   },

   computed: {
      ...mapState(useTransferStore, ["upload"]),

      state() {
         return this.upload.state
      },

      uploadState() {
         return uploadState
      },

      fileUploadStatus() {
         return uploadFileStatus
      },

      showTryAgainButton() {
         return (
           this.fileState.status === uploadFileStatus.saveFailed ||
           this.fileState.status === uploadFileStatus.uploadFailed ||
           this.fileState.status === uploadFileStatus.fileGoneInUpload ||
           this.fileState.status === uploadFileStatus.fileGoneInRequestProducer
         ) && this.state === uploadState.uploading
      },

      showDismissButton() {
         return this.fileState.status === uploadFileStatus.fileGoneInUpload ||
           this.fileState.status === uploadFileStatus.fileGoneInRequestProducer ||
           this.fileState.status === uploadFileStatus.errorOccurred ||
           this.fileState.status === uploadFileStatus.saveFailed ||
           this.fileState.status === uploadFileStatus.uploadFailed
      }
   },

   methods: {
      getFileType,
      isErrorStatus,

      dismiss() {
         getUploader().dismissFile(this.fileState.frontendId)
      },

      retry() {
         if (this.fileState.status === uploadFileStatus.saveFailed) {
            getUploader().retrySaveFailedFiles()
         } else if (this.fileState.status === uploadFileStatus.uploadFailed) {
            getUploader().retryFailedRequests()
         } else if (this.fileState.status === uploadFileStatus.fileGoneInUpload) {
            getUploader().retryGoneFile(this.fileState.frontendId)
         } else if (this.fileState.status === uploadFileStatus.fileGoneInRequestProducer) {
            getUploader().retryGoneFile(this.fileState.frontendId)
         } else {
            this.$toast.error("Can't retry, unknown state")
         }
      }
   }
}
</script>
