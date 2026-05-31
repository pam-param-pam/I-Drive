<template>
   <div class="card floating" @paste="onPaste">
      <div class="card-title">
         <h2>{{ $t("prompts.editThumbnail") }}</h2>
      </div>

      <div class="card-content">
         <div v-if="!isAdvancedExpanded">
            <p v-if="canUploadThumbnail">
               {{ $t("prompts.selectThumbnail") }}
            </p>
            <p v-else>
               {{ $t("prompts.thumbnailNotAllowed") }}
            </p>

            <div v-if="localImagePreview" class="image-preview">
               <img :src="localImagePreview" alt="Selected Thumbnail" />
            </div>

            <div class="thumbnail-options">
               <SmartFileInput
                 v-if="canUploadThumbnail"
                 ref="smartFileInput"
                 :label="$t('buttons.selectImageFile')"
                 accept="image/*"
                 @file-selected="processFile"
               />

               <button
                 v-if="file?.thumbnail_url"
                 :aria-label="$t('buttons.removeThumbnail')"
                 :disabled="uploading || removing"
                 :title="$t('buttons.removeThumbnail')"
                 class="thumbnail-remove-button"
                 type="button"
                 @click="removeCurrentThumbnail()"
               >
                  {{ $t("buttons.removeThumbnail") }}
               </button>
            </div>
         </div>


         <video
           v-if="isVideo"
           ref="video"
           class="hidden-video"
           :src="file?.download_url"
           crossorigin="anonymous"
           preload="metadata"
           @error="onVideoError"
           @loadedmetadata="onVideoMetadataLoaded"
         />

         <div v-if="isVideo" class="expandable-section">

            <div class="expandable-header" @click="toggleAdvanced">
               <strong>{{ $t("prompts.captureFromVideo") }}</strong>
               <i :class="{ expanded: isAdvancedExpanded }" class="material-icons expand-icon">
                  keyboard_arrow_down
               </i>
            </div>

            <div v-if="isAdvancedExpanded" class="expandable-content">
               <p v-if="videoError">
                  {{ $t("prompts.videoThumbnailError") }}
               </p>
               <div v-else-if="videoFramePreview && !isCapturingFrame && videoReady" class="image-preview">
                  <img :src="videoFramePreview" alt="Selected Thumbnail" />
               </div>
               <div v-else class="image-preview skeleton-preview">
                  <div class="skeleton-image"></div>
               </div>

               <label v-if="!videoError" class="thumbnail-time-label">
                  {{ $t("prompts.thumbnailSecond") }}
               </label>

               <div v-if="!videoError" class="thumbnail-time-controls">
                  <input
                    v-model.number="thumbnailSecond"
                    :max="videoDuration"
                    min="0"
                    step="0.1"
                    type="number"
                    class="thumbnail-second-input"
                  />

                  <input
                    v-model.number="thumbnailSecond"
                    :max="videoDuration"
                    min="0"
                    step="0.1"
                    type="range"
                    class="thumbnail-second-slider"
                  />
               </div>

            </div>
         </div>

         <div v-if="uploading" class="prompts-progress-bar-wrapper">
            <ProgressBar :progress="uploadProgress" />
            <span>
               <b>{{ uploadProgress }}%</b>
            </span>
         </div>
      </div>

      <div class="card-action">
         <button
           :aria-label="$t('buttons.cancel')"
           :title="$t('buttons.cancel')"
           class="button button--flat button--grey"
           @click="cancel()"
         >
            {{ $t("buttons.cancel") }}
         </button>

         <button
           v-if="canUploadThumbnail"
           :aria-label="$t('buttons.upload')"
           :disabled="isUploadDisabled"
           :title="$t('buttons.upload')"
           class="button button--flat"
           @click="submit()"
         >
            {{ $t("buttons.upload") }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { upload } from "@/upload/utils/uploadHelper.js"
import { createThumbnail, deleteThumbnail } from "@/api/files.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { canUpload } from "@/api/user.js"
import ProgressBar from "@/components/upload/UploadProgressBar.vue"
import axios from "axios"
import { filesize } from "@/utils/index.js"
import { encrypt, generateIv, generateKey } from "@/upload/utils/encryption.js"
import SmartFileInput from "@/components/SmartFileInput.vue"
import { getMomentFrame } from "@/upload/utils/thumbnailHelper.js"
import { backendInstance } from "@/axios/networker.js"

export default {
   name: "edit-thumbnail",

   components: { SmartFileInput, ProgressBar },

   data() {
      return {
         thumbnailFile: null,
         localImagePreview: null,
         uploadProgress: 0,
         uploading: false,
         removing: false,
         cancelTokenSource: null,
         thumbnailSecond: 0,
         videoDuration: 0,
         videoReady: false,
         currentThumbnailData: null,
         isCapturingFrame: false,
         isAdvancedExpanded: false,
         videoFramePreview: null,
         videoFile: null,
         videoError: false
      }
   },

   computed: {
      ...mapState(useMainStore, ["user", "selected"]),
      ...mapState(useUploadStore, ["attachmentName"]),

      file() {
         return this.selected[0]
      },

      isVideo() {
         return this.file?.type === "Video"
      },

      canUploadThumbnail() {
         let thumbnailTypes = ["Image", "Raw image", "Video", "Audio"]
         return thumbnailTypes.some(type => this.file?.type?.includes(type))
      },
      isUploadDisabled() {
         if (this.uploading || this.removing) return true
         if (this.isAdvancedExpanded) {
            return !this.videoFile || this.videoError || this.isCapturingFrame
         } else {
            return !this.thumbnailFile
         }
      }
   },

   watch: {
      thumbnailSecond() {
         if (!this.isVideo || !this.videoReady) return
         this.captureFrame()
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      toggleAdvanced() {
         this.isAdvancedExpanded = !this.isAdvancedExpanded
      },

      onPaste(event) {
         if (this.isAdvancedExpanded) return
         let items = (event.clipboardData || window.clipboardData).items
         for (let item of items) {
            if (item.type.startsWith("image/")) {
               let file = item.getAsFile()
               this.processFile(file)
               break
            }
         }
      },
      async onVideoError() {
         this.videoError = true
         await backendInstance.get(this.file.download_url, {
            headers: {
               Range: `bytes=0-1`
            },
            __skipAuth: true,
         })
      },

      processFile(file) {
         if (!file || !file.type.startsWith("image/")) {
            this.$toast.error(this.$t("toasts.thumbnailInvalid"))
            this.$refs.smartFileInput.reset()
            return
         }

         let maxSize = this.user.maxDiscordMessageSize
         if (file.size >= maxSize) {
            this.$toast.error(this.$t("toasts.fileTooBig", { max: filesize(maxSize) }))
            this.$refs.smartFileInput.reset()
            return
         }

         this.thumbnailFile = file
         this.currentThumbnailData = null

         let reader = new FileReader()
         reader.onload = (e) => {
            this.localImagePreview = e.target.result
         }
         reader.readAsDataURL(file)
      },

      onVideoMetadataLoaded() {
         let video = this.$refs.video
         if (!video) return

         this.videoDuration = Number.isFinite(video.duration) ? video.duration : 0
         this.videoReady = true

         this.captureFrame()
      },

      seekVideoToThumbnailSecond() {
         return new Promise((resolve) => {
            let video = this.$refs.video
            if (!video) {
               resolve()
               return
            }

            let targetSecond = Math.min(Math.max(this.thumbnailSecond || 0, 0), this.videoDuration || 0)

            let onSeeked = () => {
               video.removeEventListener("seeked", onSeeked)
               resolve()
            }

            video.addEventListener("seeked", onSeeked)
            video.currentTime = targetSecond
         })
      },

      async captureFrame() {
         if (!this.isVideo || !this.videoReady || this.isCapturingFrame) return

         this.isCapturingFrame = true
         try {
            await this.seekVideoToThumbnailSecond()
            const frameBlob = await getMomentFrame(this.$refs.video)
            if (frameBlob) {
               if (this.videoFramePreview && this.videoFramePreview.startsWith('blob:')) {
                  URL.revokeObjectURL(this.videoFramePreview)
               }
               this.videoFramePreview = URL.createObjectURL(frameBlob)
               this.videoFile = new File([frameBlob], "video-thumbnail.webp", { type: frameBlob.type || "image/webp" })
            }
         } catch (err) {
            console.warn("Failed to capture video frame", err)
         } finally {
            this.isCapturingFrame = false
         }
      },

      async submit() {
         if (this.uploading || this.removing) return

         try {
            this.uploading = true
            this.uploadProgress = 0

            let res = await canUpload(this.file.parent_id)
            if (!res.can_upload) {
               this.uploading = false
               return
            }

            const fileToUpload = this.isAdvancedExpanded ? this.videoFile : this.thumbnailFile
            if (!fileToUpload) {
               this.$toast.error(this.$t("toasts.noFileSelected"))
               this.uploading = false
               return
            }

            let method = this.file.encryption_method
            let iv = generateIv(method)
            let key = generateKey(method)

            let encryptedBlob = await encrypt(fileToUpload, method, key, iv, 0)

            this.cancelTokenSource = axios.CancelToken.source()
            let fileFormList = new FormData()
            fileFormList.append("file", encryptedBlob, this.attachmentName)

            let config = {
               onUploadProgress: (progressEvent) => {
                  if (progressEvent.total) {
                     this.uploadProgress = Math.round((progressEvent.loaded / progressEvent.total) * 100)
                  }
               },
               cancelToken: this.cancelTokenSource.token
            }

            let uploadResponse = await upload(fileFormList, config)

            let thumbnail_data = {
               size: encryptedBlob.size,
               channel_id: uploadResponse.data.channel_id,
               message_id: uploadResponse.data.id,
               attachment_id: uploadResponse.data.attachments[0].id,
               iv: iv,
               key: key,
               message_author_id: uploadResponse.data.author.id
            }

            await createThumbnail(this.file.id, thumbnail_data)
            this.$toast.success(this.$t("toasts.thumbnailChanged"))
            this.closeHover()
         } catch (error) {
            if (axios.isCancel(error)) return
            console.error("Upload error:", error)
            this.$toast.error(this.$t("toasts.thumbnailUploadFailed"))
         } finally {
            this.uploading = false
            this.uploadProgress = 0
         }
      },

      async removeCurrentThumbnail() {
         if (this.uploading || this.removing) return

         try {
            this.removing = true
            await deleteThumbnail(this.file.id)
            this.$toast.success(this.$t("toasts.thumbnailRemoved"))
            this.closeHover()
         } finally {
            this.removing = false
         }
      },

      cancel() {
         if (this.cancelTokenSource) {
            this.cancelTokenSource.cancel("Upload has been canceled by the user.")
         }
         this.closeHover()
      }
   }
}
</script>

<style scoped>
.thumbnail-options {
   display: flex;
   flex-direction: column;
   gap: 0.75rem;
   width: 100%;
}

.hidden-video {
   display: none;
}

.image-preview {
   margin-top: 15px;
   padding-bottom: 1em;
   display: flex;
   justify-content: center;
   align-items: center;
}

.image-preview img {
   max-width: 100%;
   max-height: 200px;
   border-radius: 5px;
   box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

.skeleton-preview {
   width: 100%;
   min-height: 200px;
   border-radius: 5px;
   display: flex;
   justify-content: center;
   align-items: center;
}

.skeleton-image {
   width: 100%;
   height: 200px;
   background: linear-gradient(90deg, var(--divider) 25%, var(--background) 50%, var(--divider) 75%);
   background-size: 200% 100%;
   animation: skeleton-loading 1.5s infinite;
   border-radius: 5px;
}

@keyframes skeleton-loading {
   0% {
      background-position: 200% 0;
   }
   100% {
      background-position: -200% 0;
   }
}

.thumbnail-remove-button {
   width: 100%;
   min-height: 48px;
   border: transparent;
   border-radius: 5px;
   background: transparent;
   color: #ff8a8a;
   font-size: 14px;
   font-weight: 600;
   cursor: pointer;
}

.thumbnail-remove-button:hover:not(:disabled) {
   background: rgba(255, 120, 120, 0.08);
}

.thumbnail-remove-button:disabled {
   opacity: 0.45;
   cursor: not-allowed;
}

.expandable-header {
   color: var(--textSecondary);
}

.expandable-header strong {
   font-weight: 600;
}

.expand-icon {
   transition: transform 0.2s ease;
}

.expand-icon.expanded {
   transform: rotate(180deg);
}

.expandable-content {
   padding-bottom: 1rem;
}

.thumbnail-time-label {
   display: block;
   margin-bottom: 0.5rem;
   color: var(--textPrimary);
   font-size: 14px;
}

.thumbnail-time-controls {
   display: flex;
   gap: 0.75rem;
   align-items: center;
}

.thumbnail-second-input {
   width: 90px;
   min-height: 40px;
   padding: 0 0.5rem;
   border: 1px solid var(--divider);
   border-radius: 5px;
   background: var(--background);
   color: var(--textPrimary);
}

.thumbnail-second-slider {
   flex: 1;
}

.thumbnail-frame-button {
   width: 100%;
   min-height: 44px;
   margin-top: 0.85rem;
   border: 1px solid var(--divider);
   border-radius: 5px;
   background: var(--divider);
   color: var(--textPrimary);
   font-size: 14px;
   font-weight: 600;
   cursor: pointer;
}

.thumbnail-frame-button:hover:not(:disabled) {
   filter: brightness(1.08);
}

.thumbnail-frame-button:disabled {
   opacity: 0.45;
   cursor: not-allowed;
}

.prompts-progress-bar-wrapper {
   margin-top: 1rem;
}
</style>