<template>
   <div
      :class="{
         'failed-border': file.status === uploadStatus.failed,
         'success-border': file.status === uploadStatus.uploaded,
         'paused-border':
            file.status === uploadStatus.paused || file.status === uploadStatus.pausing,
         'uploading-border': file.status === uploadStatus.uploading,
         'shake-animation': isShaking
      }"
      class="fileitem-wrapper"
   >
      <!-- Upper -->
      <div class="fileitem-header file-icons">
         <div :data-type="type" :aria-label="file.extension">
            <i class="material-icons file-icon"></i>
         </div>

         <span class="file-name">{{ file.name }}</span>
               <div class="button-group">
         <!--        <button-->
         <!--          v-if="showPauseButton"-->
         <!--          class="pause-button"-->
         <!--          @click="togglePause">-->
         <!--          <i class="material-icons">{{ file.status === 'paused' ? 'play_arrow' : 'pause' }}</i>-->
         <!--        </button>-->
         <!--        <button-->
         <!--          v-if="showCancelButton"-->
         <!--          class="cancel-button"-->
         <!--          @mouseover="startShake"-->
         <!--          @mouseleave="stopShake"-->
         <!--          @click="cancel"-->
         <!--        >-->
         <!--          <i class="material-icons">close</i>-->
         <!--        </button>-->
                 <button
                   v-if="showTryAgainButton"
                   class="pause-button"
                   @click="retry"
                 >
                   <i class="material-icons">refresh</i>
                 </button>
               </div>
      </div>

      <!-- Lower -->
      <div v-if="file.status && isInternet">
         <span v-if="file.status === uploadStatus.creating">
            <b class="creating">{{ $t('uploadFile.creating') }}</b>
         </span>
         <span v-if="file.status === uploadStatus.finishing">
            <b class="creating">{{ $t('uploadFile.finishing') }}</b>
         </span>
         <span v-if="file.status === uploadStatus.encrypting">
            <b class="creating">{{ $t('uploadFile.encrypting') }}</b>
         </span>
         <span v-if="file.status === uploadStatus.failed">
            <b class="failed">{{ $t('uploadFile.failed') }}</b>
         </span>
         <span v-if="file.status === uploadStatus.preparing">
            <b class="creating">{{ $t('uploadFile.preparingUpload') }}</b>
         </span>
         <span v-if="file.status === uploadStatus.uploaded">
            <b class="success">{{ $t('uploadFile.success') }}</b>
         </span>
         <span v-if="file.status === uploadStatus.paused">
            <b class="paused">{{ $t('uploadFile.paused') }}</b>
         </span>
         <div
            v-if="file.status === uploadStatus.uploading || file.status === uploadStatus.pausing"
            class="fileitem-progress"
         >
            <ProgressBar :progress="file.progress" />
            <span>
               <b> {{ file.progress }}% </b>
            </span>
         </div>
      </div>
      <div v-if="!isInternet">
         <span>
            <b class="failed">{{ $t('uploadFile.noInternet') }}</b>
         </span>
      </div>
   </div>
</template>

<script>
import ProgressBar from '@/components/upload/UploadProgressBar.vue'
import { mapActions, mapState } from 'pinia'
import { useUploadStore } from '@/stores/uploadStore.js'
import { fileUploadStatus } from '@/utils/constants.js'
import { useMainStore } from '@/stores/mainStore.js'

export default {
   components: { ProgressBar },

   props: ['file'],

   data() {
      return {
         isPaused: false,
         isShaking: false
      }
   },

   computed: {
      type() {
         let splitMimetype =  this.file.type.split("/")[0]
         if (splitMimetype === 'application') return 'pdf'
         if (!splitMimetype) return 'text'
         return splitMimetype
      },
      uploadStatus() {
         return fileUploadStatus
      },

      ...mapState(useUploadStore, ['isInternet']),
      ...mapState(useMainStore, ['user']),
      showPauseButton() {
         return (
            (this.file.status === fileUploadStatus.uploading ||
               this.file.status === fileUploadStatus.resuming ||
               this.file.status === fileUploadStatus.pausing ||
               this.file.status === fileUploadStatus.paused) &&
            this.isInternet &&
            this.file.size > this.user.maxDiscordMessageSize
         )
      },
      showTryAgainButton() {
         return (this.file.status === fileUploadStatus.failed)
      },
      showCancelButton() {
         return (
            this.file.status === fileUploadStatus.uploading &&
            this.isInternet &&
            this.file.size > this.user.maxDiscordMessageSize
         )
      }
   },

   methods: {
      ...mapActions(useUploadStore, ['pauseFile', 'resumeFile', 'cancelFile', 'tryAgain']),

      togglePause() {
         if (this.file.status === fileUploadStatus.paused) {
            this.resumeFile(this.file.frontendId)
         } else if (this.file.status === fileUploadStatus.uploading) {
            this.pauseFile(this.file.frontendId)
         }
      },

      retry() {
         this.tryAgain(this.file.frontendId)
      },

      cancel() {
         if (!(this.file.status === fileUploadStatus.uploading)) return
         this.cancelFile(this.file.frontendId)
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

<style lang="scss" scoped>
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

.failed {
   color: red;
}

.failed-border {
   border-color: red;
}

.success {
   color: green;
}

.success-border {
   border-color: green;
}

.paused {
   color: orange;
}

.paused-border {
   border-color: orange;
}

.waiting {
   color: #57e9f6;
}

.paused-border {
   border-color: orange;
}

.uploading-border {
}

.button-group {
   display: flex;
   gap: 0.5rem;
   margin-left: 1em;
   border-radius: 15px
}

.button-group:hover {
   background-color: var(--moon-grey);

}

.cancel-button,
.pause-button {
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

.cancel-button:hover {
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
