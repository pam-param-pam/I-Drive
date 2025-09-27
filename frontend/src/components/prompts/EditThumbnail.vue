<template>
  <div class="card floating" @paste="onPaste">
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
        <input id="fileInput" accept="image/*" type="file" @change="onFileInput" />
        <label class="file-label" for="fileInput">
          {{ thumbnailFile ? thumbnailFile.name : $t("buttons.addSubtitleFile") }}
        </label>
      </div>
      <div v-if="uploading" class="prompts-progress-bar-wrapper">
        <ProgressBar :progress="uploadProgress" />
        <span>
               <b> {{ uploadProgress }}% </b>
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
        :aria-label="$t('buttons.upload')"
        :disabled="!thumbnailFile"
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
import { encrypt } from "@/utils/encryption.js"
import { generateIv, generateKey, upload } from "@/upload/uploadHelper.js"
import { createThumbnail } from "@/api/files.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { canUpload } from "@/api/user.js"
import ProgressBar from "@/components/upload/UploadProgressBar.vue"
import axios from "axios"
import { filesize } from "@/utils/index.js"

export default {
   name: "edit-thumbnail",

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
      ...mapState(useUploadStore, ["attachmentName"]),

      file() {
         return this.selected[0]
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "updateItem"]),

      onFileInput(event) {
         this.processFile(event.target.files[0])
      },

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
            return
         }

         let maxSize = this.user.maxDiscordMessageSize
         if (file.size >= maxSize) {
            this.$toast.error(this.$t("toasts.fileTooBig", { max: filesize(maxSize) }))
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
                     this.uploadProgress = Math.round(
                        (progressEvent.loaded / progressEvent.total) * 100
                     )
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
            if (error.code === "ERR_CANCELED") return
            this.$toast.error(this.$t("toasts.thumbnailUploadFailed"))
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
</style>
