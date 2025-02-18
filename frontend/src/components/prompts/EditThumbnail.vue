<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.editThumbnail") }}</h2>
    </div>

    <div class="card-content">
      <p>
        {{ $t("prompts.selectThumbnail") }}
      </p>
      <div v-if="imagePreview" class="image-preview">
        <img :src="imagePreview" alt="Selected Thumbnail" />
      </div>
      <div class="file-input-wrapper">
        <input
          type="file"
          id="fileInput"
          accept="image/*"
          @change="onFileInput"
        />
        <label for="fileInput" class="file-label">
          {{ thumbnailFile ? thumbnailFile.name : $t("buttons.chooseFile") }}
        </label>
      </div>
      <div v-if="uploading" class="progress-bar-wrapper">
        <ProgressBar
          :progress="uploadProgress"
        />
        <span>
          <b> {{ uploadProgress }}% </b>
        </span>
      </div>
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="cancel()"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        class="button button--flat"
        :disabled="!thumbnailFile"
        @click="submit()"
        :aria-label="$t('buttons.upload')"
        :title="$t('buttons.upload')"
      >
        {{ $t("buttons.upload") }}
      </button>
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { encryptionMethod } from "@/utils/constants.js"
import { encryptWithAesCtr, encryptWithChaCha20 } from "@/utils/encryption.js"
import { generateIv, generateKey } from "@/utils/uploadHelper.js"
import { discordInstance } from "@/utils/networker.js"
import { createThumbnail } from "@/api/files.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { canUpload } from "@/api/user.js"
import i18n from "@/i18n/index.js"
import ProgressBar from "@/components/upload/UploadProgressBar.vue"
import axios from "axios"
import { filesize } from "@/utils/index.js"

export default {
   name: "file-upload-prompt",
   components: { ProgressBar },
   data() {
      return {
         thumbnailFile: null,
         imagePreview: null,
         uploadProgress: 0,
         uploading: false,
         cancelTokenSource: null


      }
   },
   computed: {
      ...mapState(useMainStore, ["user", "selected"]),
      ...mapState(useUploadStore, ["webhooks", "attachmentName"]),

      file() {
         return this.selected[0]
      }

   },
   methods: {
      ...mapActions(useMainStore, ["closeHover", "updateItem"]),

      onFileInput(event) {
         let file = event.target.files[0]

         if (!file.type.startsWith("image/")) {
            this.$toast.error(this.$t("toasts.thumbnailInvalid"))
            return
         }
         let maxSize = this.user.maxDiscordMessageSize
         if (file && file.size >= maxSize) {
            this.$toast.error(this.$t("toasts.thumbnailFileTooBig", { "max": filesize(maxSize) }))
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
         if (this.uploading) return

         this.uploading = true
         this.uploadProgress = 0


         let res = await canUpload(this.file.parent_id)
         if (!res.can_upload) {
            this.$toast.error(this.$t("errors.notAllowedToUpload"))
            this.uploading = false
            return
         }

         let webhook = this.webhooks[0]
         let formData = new FormData()
         let content = this.thumbnailFile
         let iv
         let key

         //todo this is cursed
         this.file.encryptionMethod = this.file.encryption_method

         if (this.file.encryption_method !== encryptionMethod.NotEncrypted) {
            // Ensure content is a Blob before encrypting
            if (typeof content === "string") {
               content = new Blob([content])
            }
            iv = generateIv(this.file)
            key = generateKey()

            if (this.file.encryption_method === encryptionMethod.ChaCha20) {
               content = await encryptWithChaCha20(key, iv, content, 0)

            } else if (this.file.encryption_method === encryptionMethod.AesCtr) {
               content = await encryptWithAesCtr(key, iv, content, 0)
            }

         }
         let blob = new Blob([content])
         this.cancelTokenSource = axios.CancelToken.source()

         formData.append("file", blob, this.attachmentName)
         try {
            let discordResponse = await discordInstance.post(webhook.url, formData, {
               headers: {
                  "Content-Type": "multipart/form-data"
               },
               onUploadProgress: (progressEvent) => {
                  if (progressEvent.total) {
                     this.uploadProgress = Math.round((progressEvent.loaded / progressEvent.total) * 100)
                  }
               },
               cancelToken: this.cancelTokenSource.token
            })

            let file_data = {
               "file_id": this.file.id,
               "size": content.size,
               "message_id": discordResponse.data.id,
               "attachment_id": discordResponse.data.attachments[0].id,
               "iv": iv,
               "key": key,
               "webhook": webhook.discord_id
            }
            await createThumbnail(file_data)
            this.closeHover()

         } catch (error) {
            if (error.code === "ERR_CANCELED") return
            this.$toast.error(this.$t("prompts.thumbnailUploadFailed"))
            this.uploading = false
            this.uploadProgress = 0
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

input[type="file"] {
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

.progress-bar-wrapper {
 padding-top: 1em;
 padding-right: 0.5em;
 padding-left: 0.5em;
 display: flex;
 gap: 1rem;
 align-items: center;

}
</style>
