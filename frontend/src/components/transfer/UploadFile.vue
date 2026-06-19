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
      <!-- Upper -->
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
            <b class="error">{{ $t("uploadFile.fatal") }}</b>
         </span>
      </div>
      <div v-else-if="state === uploadState.noInternet">
         <span>
            <b class="error">{{ $t("uploadFile.noInternet") }}</b>
         </span>
      </div>
      <div v-else-if="state === uploadState.paused && !isErrorStatus(fileState.status)">
         <span>
            <b class="warning">{{ $t("uploadFile.paused") }}</b>
         </span>
      </div>
      <!-- Lower -->
      <div v-else-if="fileState.status">
         <span v-if="fileState.status === fileUploadStatus.preparing">
            <b class="info">{{ $t("uploadFile.preparing") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.waitingForInternet">
            <b class="info">{{ $t("uploadFile.waitingForInternet") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.retrying">
            <b class="info">{{ $t("uploadFile.retrying") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.uploaded">
            <b class="success">{{ $t("uploadFile.success") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.waitingForSave">
            <b class="success">{{ $t("uploadFile.waitingForSave") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.paused">
            <b class="warning">{{ $t("uploadFile.paused") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.saveFailed">
            <b v-if="fileState.error" class="error">{{ fileState.error.details }}</b>
            <b v-else class="error">{{ $t("uploadFile.saveFailed") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.uploadFailed">
            <b v-if="fileState.error" class="error">{{ fileState.error }}</b>
            <b v-else class="error">{{ $t("uploadFile.uploadFailed") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.errorOccurred">
            <b v-if="fileState.error" class="error">{{ fileState.error }}</b>
            <b v-else class="error">{{ $t("uploadFile.failed") }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.fileGoneInRequestProducer || fileState.status === fileUploadStatus.fileGoneInUpload">
            <b class="error">{{ $t("uploadFile.fileGone") }}</b>
         </span>
         <div
            v-if="fileState.status === fileUploadStatus.uploading"
            class="fileitem-progress"
         >
            <TransferProgressBar :progress="fileState.progress" />
            <span>
               <b> {{ fileState.progress }}% </b>
            </span>
         </div>
      </div>

   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useUploadStore } from "@/stores/uploadStore.js"
import { uploadFileStatus, uploadState } from "@/utils/constants.js"
import { getFileType, isErrorStatus } from "@/transfers/upload/utils/uploadHelper.js"
import { getUploader } from "@/transfers/upload/Uploader.js"
import TransferProgressBar from "@/components/transfer/TransferProgressBar.vue"

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
      ...mapState(useUploadStore, ["state"]),
      uploadState() {
         return uploadState
      },
      fileUploadStatus() {
         return uploadFileStatus
      },
      showTryAgainButton() {
         return (this.fileState.status === uploadFileStatus.saveFailed ||
               this.fileState.status === uploadFileStatus.uploadFailed ||
               this.fileState.status === uploadFileStatus.fileGoneInUpload ||
               this.fileState.status === uploadFileStatus.fileGoneInRequestProducer) &&
            this.state === uploadState.uploading
      },
      showDismissButton() {
         return (this.fileState.status === uploadFileStatus.fileGoneInUpload ||
            this.fileState.status === uploadFileStatus.fileGoneInRequestProducer ||
            this.fileState.status === uploadFileStatus.errorOccurred ||
            this.fileState.status === uploadFileStatus.saveFailed ||
            this.fileState.status === uploadFileStatus.uploadFailed
         )
      }
   },

   methods: {
      getFileType,
      isErrorStatus,
      ...mapActions(useUploadStore, ["dismissFile", "retryGoneFile"]),
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
            this.$toast.error("Can't retry, unknown state") //todo
         }
      }
   }
}
</script>

<style scoped>

</style>
