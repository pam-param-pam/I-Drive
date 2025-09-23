<template>
   <div v-if="filesInUploadCount > 0" class="upload-files" v-bind:class="{ closed: !open }">
      <div class="card floating">
         <div class="card-title">
            <h2 v-if="state !== uploadState.idle && state !== uploadState.paused">
               {{ $t('prompts.uploadFiles', { amount: filesInUploadCount }) }}
            </h2>
            <h2 v-if="state === uploadState.paused">
               {{ $t('prompts.pausedFilesUpload', { amount: filesInUploadCount }) }}
            </h2>
            <div v-if="state === uploadState.uploading" class="upload-info">
               <div class="upload-speed">{{ filesize(uploadSpeed) }}/s</div>
               <div class="upload-eta">{{ formattedETA }} remaining</div>
            </div>

            <div class="action-buttons">
               <button
                 v-if="state === uploadState.noInternet && !isAllUploadsFinished"
                 :aria-label="$t('uploadFile.retry')"
                 :title="$t('uploadFile.retry')"
                 class="action"
                 @click="retry"
               >
                  <i class="material-icons">refresh</i>
               </button>
               <button
                  v-if="state === uploadState.uploading && !isAllUploadsFinished"
                  :aria-label="$t('uploadFile.pause')"
                  :title="$t('uploadFile.pause')"
                  class="action"
                  @click="pause"
               >
                  <i class="material-icons">pause</i>
               </button>
               <button
                  v-if="state === uploadState.paused && !isAllUploadsFinished"
                  :aria-label="$t('uploadFile.pause')"
                  :title="$t('uploadFile.pause')"
                  class="action"
                  @click="resume"
               >
                  <i class="material-icons">play_arrow</i>
               </button>
               <button
                  :aria-label="$t('uploadFile.toggleUploadList')"
                  :title="$t('uploadFile.toggleUploadList')"
                  class="action"
                  @click="toggle"
               >
                  <i class="material-icons">{{
                     open ? 'keyboard_arrow_down' : 'keyboard_arrow_up'
                  }}</i>
               </button>
            </div>
         </div>
         <div class="card-content">
            <UploadFile
               v-for="fileState in filesInUpload"
               :key="fileState.frontedId"
               :aria-label="fileState.fileObj.name"
               :data-dir="false"
               :data-type="fileState.fileObj.type"
               :fileState="fileState"
            />
         </div>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from 'pinia'
import { useUploadStore } from '@/stores/uploadStore.js'
import { filesize } from '@/utils/index.js'
import UploadFile from '@/components/upload/UploadFile.vue'
import upload from '@/components/prompts/Upload.vue'
import { uploadState } from '@/utils/constants.js'

export default {
   name: 'uploadFiles',

   components: { UploadFile },

   data() {
      return {
         open: true
      }
   },

   computed: {
      ...mapState(useUploadStore, ["filesInUpload", "filesInUploadCount", "uploadSpeed", "eta", "state", "isAllUploadsFinished"]),
      uploadState() {
         return uploadState
      },
      upload() {
         return upload
      },

      formattedETA() {
         if (!this.eta || this.eta === Infinity) {
            return '--:--:--'
         }

         let totalSeconds = this.eta
         let hours = Math.floor(totalSeconds / 3600)
         totalSeconds %= 3600
         let minutes = Math.floor(totalSeconds / 60)
         let seconds = Math.round(totalSeconds % 60)

         return `${hours.toString().padStart(2, '0')}:${minutes
            .toString()
            .padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
      }
   },

   methods: {
      ...mapActions(useUploadStore, ['abortAll', 'pauseAll', 'resumeAll', 'retryAll']),

      filesize,

      toggle() {
         this.open = !this.open
      },
      retry() {
         this.retryAll()
      },
      pause() {
         this.pauseAll()
      },
      resume(event) {
         if (event.ctrlKey && event.shiftKey) {
            this.forceUnstuck()
            return
         }
         this.resumeAll()
      }
   }
}
</script>
