<template>
   <div class="card floating" @paste="onPaste">
      <div class="card-title">
         <h2>{{ $t("prompts.editThumbnail") }}</h2>
      </div>

      <div class="card-content">
         <p v-if="canUploadThumbnail">
            {{ $t("prompts.selectThumbnail") }}
         </p>
         <p v-else>
            {{ $t("prompts.thumbnailNotAllowed") }}
         </p>

         <div v-if="imagePreview" class="image-preview">
            <img :src="imagePreview" alt="Selected Thumbnail" />
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
           :disabled="!thumbnailFile || uploading || removing"
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

export default {
   name: "edit-thumbnail",

   components: { SmartFileInput, ProgressBar },

   data() {
      return {
         thumbnailFile: null,
         imagePreview: null,
         uploadProgress: 0,
         uploading: false,
         removing: false,
         cancelTokenSource: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["user", "selected"]),
      ...mapState(useUploadStore, ["attachmentName"]),

      file() {
         return this.selected[0]
      },
      canUploadThumbnail() {
         let thumbnailTypes = ["Image", "Raw image", "Video", "Audio"]
         return thumbnailTypes.some(type => this.file.type?.includes(type))
      },
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      onPaste(event) {
         let items = (event.clipboardData || window.clipboardData).items
         for (let item of items) {
            if (item.type.startsWith("image/")) {
               let file = item.getAsFile()
               this.processFile(file)
               break
            }
         }
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

         let reader = new FileReader()
         reader.onload = (e) => {
            this.imagePreview = e.target.result
         }
         reader.readAsDataURL(file)
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

            let fileFormList = new FormData()

            let method = this.file.encryption_method
            let iv = generateIv(method)
            let key = generateKey(method)
            let encryptedBlob = await encrypt(this.thumbnailFile, method, key, iv, 0)

            this.cancelTokenSource = axios.CancelToken.source()

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
            this.$toast.error(this.$t("toasts.thumbnailUploadFailed"))
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
.file-input-wrapper {
   position: relative;
   display: flex;
   align-items: center;
   width: 100%;
}

input[type='file'] {
   opacity: 0;
   width: 0;
   height: 0;
   position: absolute;
}

.file-label {
   display: inline-block;
   padding: 10px 15px;
   background-color: var(--divider);
   color: var(--textPrimary);
   border-radius: 5px;
   cursor: pointer;
   text-align: center;
   width: 100%;
   font-size: 14px;
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
.thumbnail-remove-button {
   margin-top: 1em;
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

</style>