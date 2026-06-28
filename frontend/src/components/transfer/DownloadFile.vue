<template>
   <div
     :class="{
         'error-border': isErrorStatus || state === downloadState.error,
         'success-border': fileState.status === fileDownloadStatus.completed && state !== downloadState.noInternet,
         'warning-border': state === downloadState.paused && !isErrorStatus,
         'shake-animation': isShaking
      }"
     class="fileitem-wrapper"
     @mouseenter="startDebugHover"
     @mouseleave="stopDebugHover"
     @click="toggleDebugInfo"
   >
      <div class="fileitem-header file-icons">
         <div :aria-label="fileExtension" :data-type="fileState.fileObj.type">
            <i class="material-icons file-icon"></i>
         </div>

         <div class="file-name-container">
            <div class="file-name-row">
               <span class="file-name">{{ fileName }}</span>

               <span
                 v-if="showDebugInfo"
                 class="fileitem-debug"
               >
                  {{ transferredSize }} / {{ totalSize }}
               </span>
            </div>
         </div>

         <div class="button-group">
            <button
              v-if="showTryAgainButton"
              class="action-button"
              @click.stop="retry"
            >
               <i class="material-icons">refresh</i>
            </button>

            <button
              v-if="showDismissButton"
              class="action-button"
              @click.stop="dismiss"
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
import { filesize } from "filesize"
import TransferProgressBar from "@/components/transfer/TransferProgressBar.vue"
import { downloadFileStatus, downloadState } from "@/transfers/downloads/constants.js"
import { useTransferStore } from "@/stores/transferStore.js"
import { getDownloader } from "@/transfers/downloads/Downloader.js"

export default {
   components: { TransferProgressBar },

   props: ["fileState"],

   data() {
      return {
         isShaking: false,
         showDebugInfo: false,
         debugInfoPinned: false,
         debugHoverTimer: null
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

      transferredSize() {
         return this.formatSize(this.fileState.bytesTransferred)
      },

      totalSize() {
         return this.formatSize(this.fileState.size)
      },

      showTryAgainButton() {
         return this.fileState.status === downloadFileStatus.errorOccurred
      },

      showDismissButton() {
         return this.fileState.status === downloadFileStatus.failed ||
           this.fileState.status === downloadFileStatus.errorOccurred
      },

      isErrorStatus() {
         return this.fileState.status === downloadFileStatus.failed ||
           this.fileState.status === downloadFileStatus.errorOccurred
      }
   },

   beforeUnmount() {
      this.clearDebugHoverTimer()
   },

   methods: {
      formatSize(value) {
         return filesize(value)
      },

      startDebugHover() {
         this.clearDebugHoverTimer()

         this.debugHoverTimer = setTimeout(() => {
            this.showDebugInfo = true
         }, 700)
      },

      stopDebugHover() {
         this.clearDebugHoverTimer()

         if (!this.debugInfoPinned) {
            this.showDebugInfo = false
         }
      },

      clearDebugHoverTimer() {
         if (this.debugHoverTimer) {
            clearTimeout(this.debugHoverTimer)
            this.debugHoverTimer = null
         }
      },

      toggleDebugInfo() {
         this.debugInfoPinned = !this.debugInfoPinned
         this.showDebugInfo = this.debugInfoPinned
      },

      dismiss() {
         getDownloader().dismissFile(this.fileState.fileObj.id)
      },

      retry() {
         getDownloader().retryFile(this.fileState.fileObj.id)
      },
   }
}
</script>

<style>
.file-name-container {
   flex: 1 1 auto;
   min-width: 0;
}

.file-name-row {
   display: grid;
   grid-template-columns: minmax(0, 1fr) auto;
   align-items: start;
   column-gap: 8px;
   width: 100%;
   min-width: 0;
}

.file-name {
   min-width: 0;
   white-space: normal;
   overflow-wrap: anywhere;
   word-break: break-word;
}

.fileitem-debug {
   justify-self: end;
   white-space: nowrap;
   font-size: 0.75rem;
   opacity: 0.7;
   margin-top: 5px;
}
</style>