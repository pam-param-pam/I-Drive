<template>
   <div
      :class="{
         'error-border': fileState.status === fileUploadStatus.failed,
         'success-border': fileState.status === fileUploadStatus.uploaded,
         'warning-border': state === uploadState.paused && fileState.status !== fileUploadStatus.waitingForSave,
         'shake-animation': isShaking
      }"
      class="fileitem-wrapper"
   >
      <!-- Upper -->
      <div class="fileitem-header file-icons">
         <div :data-type="type" :aria-label="fileState.fileObj.extension">
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

      <!-- Lower -->
      <div v-if="fileState.status && state !== uploadState.noInternet && (state !== uploadState.paused || fileState.status === fileUploadStatus.waitingForSave)">
         <span v-if="fileState.status === fileUploadStatus.preparing">
            <b class="info">{{ $t('uploadFile.preparingUpload') }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.finishing">
            <b class="info">{{ $t('uploadFile.finishing') }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.encrypting">
            <b class="info">{{ $t('uploadFile.encrypting') }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.waitingForInternet">
            <b class="info">{{ $t('uploadFile.waiting') }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.uploaded">
            <b class="success">{{ $t('uploadFile.success') }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.paused">
            <b class="warning">{{ $t('uploadFile.paused') }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.failed">
            <b class="error">{{ $t('uploadFile.failed') }}</b>
         </span>
         <span v-if="fileState.status === fileUploadStatus.fileGone">
            <b class="error">{{ $t('uploadFile.fileGone') }}</b>
         </span>
         <div
            v-if="fileState.status === fileUploadStatus.uploading"
            class="fileitem-progress"
         >
            <ProgressBar :progress="fileState.progress" />
            <span>
               <b> {{ fileState.progress }}% </b>
            </span>
         </div>
      </div>
      <div v-if="state === uploadState.noInternet">
         <span>
            <b class="error">{{ $t('uploadFile.noInternet') }}</b>
         </span>
      </div>
      <div v-if="state === uploadState.paused && fileState.status !== fileUploadStatus.waitingForSave">
         <span>
            <b class="warning">{{ $t('uploadFile.paused') }}</b>
         </span>
      </div>
   </div>
</template>

<script>
import ProgressBar from '@/components/upload/UploadProgressBar.vue'
import { mapActions, mapState } from 'pinia'
import { useUploadStore } from '@/stores/uploadStore.js'
import { fileUploadStatus, uploadState } from "@/utils/constants.js"
import { useMainStore } from '@/stores/mainStore.js'

export default {
   components: { ProgressBar },

   props: ['fileState'],

   data() {
      return {
         isPaused: false,
         isShaking: false
      }
   },

   computed: {
      ...mapState(useUploadStore, ['isInternet', 'state']),
      ...mapState(useMainStore, ['user']),
      uploadState() {
         return uploadState
      },
      fileUploadStatus() {
         return fileUploadStatus
      },
      type() {
         let splitMimetype =  this.fileState.fileObj.type.split("/")[0]
         if (splitMimetype === 'application') return 'pdf'
         if (!splitMimetype) return 'text'
         return splitMimetype
      },
      showTryAgainButton() {
         return (this.fileState.status === fileUploadStatus.failed || this.fileState.status === fileUploadStatus.fileGone)
      },
      showDismissButton() {
         return (this.fileState.status === fileUploadStatus.fileGone)
      },

   },

   methods: {
      ...mapActions(useUploadStore, ['pauseAll', 'resumeAll', 'dismissFile']),
      dismiss() {
         this.dismissFile(this.file.frontendId)
      },
      retry() {

      },
      startShake() {
         this.isShaking = true
      },

      stopShake() {
         this.isShaking = false
      }
   }
}
</script>

<style scoped>
.fileitem-wrapper {
   display: flex;
   flex-direction: column;
   gap: 0.5rem;
   border: 0.15em dashed lightgray;
   border-radius: 0.5rem;
   padding: 0.5rem;
   margin-bottom: 0.4em;
}

.fileitem-header {
   display: flex;
   align-items: center;
   justify-content: space-between;
}

.file-name {
   flex: 1;
   white-space: nowrap;
   overflow: hidden;
   text-overflow: ellipsis;
}

.fileitem-progress {
   display: flex;
   gap: 1rem;
   align-items: center;
}

.error {
   color: red;
}

.error-border {
   border-color: red;
}

.success {
   color: green;
}

.success-border {
   border-color: green;
}

.warning {
   color: orange;
}

.warning-border {
   border-color: orange;
}

.info {
   color: #a9a9a9;
}



.button-group {
   display: flex;
   gap: 0.5rem;
   margin-left: 1em;
   border-radius: 15px
}

.action-button:hover {
   background-color: var(--surfaceSecondary);
}

.action-button {
   background: none;
   border: none;
   padding: 0;
   margin: 0;
   cursor: pointer;
   border-radius: 50%;
   display: flex;
   align-items: center;
   justify-content: center;
   transition: background-color 0.3s;
}

.button-red:hover {
   color: red;
}

.material-icons {
   font-size: 22px;
   vertical-align: middle;
}

@keyframes shake {
   0% {
      transform: translate(0, 0);
   }
   17% {
      transform: translate(-1px, -1px);
   }
   34% {
      transform: translate(1px, -1px);
   }
   51% {
      transform: translate(-1px, 1px);
   }
   68% {
      transform: translate(1px, 1px);
   }
   85% {
      transform: translate(-1px, -1px);
   }
   100% {
      transform: translate(0, 0);
   }
}

.shake-animation {
   animation: shake 0.3s ease infinite;
   border-color: red;
}

.file-icons .file-icon {
   color: var(--color-text);
   padding-right: 10px;
}
</style>
