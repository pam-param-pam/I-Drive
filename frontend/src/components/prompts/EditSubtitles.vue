<template>
  <div class="card floating subtitle-manager">
    <div class="card-title">
      <h2>{{ $t("prompts.manageSubtitles") }}</h2>
    </div>

    <div class="card-content">
      <p v-if="subtitles.length !== 0">{{ $t("prompts.existingSubtitles") }}</p>
      <ul class="subtitle-list">
        <li v-for="(sub) in subtitles" :key="sub.id">
          <label>
            {{ sub.language }}
          </label>
          <button class="action remove" @click="removeSubtitle(sub.id)">
            <i class="material-icons">delete</i>
          </button>
        </li>
      </ul>

      <hr v-if="subtitles.length !== 0" />

      <p>{{ $t("prompts.addSubtitle") }}</p>
      <div class="input-group input">
        <label for="langInput">{{ $t("prompts.subtitleLanguage") }}</label>
        <input
          id="langInput"
          v-model.trim="newLanguage"
          placeholder="english"
          class="input input--block"
        />
      </div>
      <div v-if="uploading" class="progress-bar-wrapper">
        <ProgressBar :progress="uploadProgress" />
        <span>
               <b> {{ uploadProgress }}% </b>
            </span>
      </div>
      <div class="file-input-wrapper">
        <input
          id="subtitleInput"
          accept=".vtt"
          type="file"
          @change="onSubtitleInput"
        />
        <label class="file-label" for="subtitleInput">
          {{ newSubtitleFile ? newSubtitleFile.name : $t("buttons.addSubtitleFile") }}
        </label>
      </div>

    </div>

    <div class="card-action">
      <button class="button button--flat button--grey" @click="$emit('close')">
        {{ $t("buttons.cancel") }}
      </button>
      <button
        class="button button--flat"
        :disabled="!canSubmit"
        @click="addSubtitle"
      >
        {{ $t("buttons.save") }}
      </button>
    </div>
  </div>
</template>

<script>
import { addSubtitle, getSubtitles, removeSubtitle } from "@/api/files.js"
import { filesize } from "@/utils/index.js"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { canUpload } from "@/api/user.js"
import { generateIv, generateKey, upload } from "@/utils/uploadHelper.js"
import { encrypt } from "@/utils/encryption.js"
import axios from "axios"
import ProgressBar from "@/components/upload/UploadProgressBar.vue"

export default {
   name: "manage-subtitles",
   components: { ProgressBar },
   data() {
      return {
         subtitles: [],
         newSubtitleFile: null,
         newLanguage: "",
         cancelTokenSource: null,
         uploadProgress: 0,
         uploading: false
      }
   },
   computed: {
      ...mapState(useMainStore, ["user", "selected"]),

      canSubmit() {
         return this.newSubtitleFile && this.newLanguage.length > 0
      }
   },
   async mounted() {
      this.subtitles = await getSubtitles(this.selected[0]?.id)
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      onSubtitleInput(event) {
         let file = event.target.files[0]
         if (!file) return

         if (!file.name.endsWith(".vtt")) {
            this.$toast.error(this.$t("toasts.invalidSubtitleFormat"))
            return
         }

         this.newSubtitleFile = file
      },
      async addSubtitle() {
         if (!this.canSubmit) return

         if (this.uploading) return

         this.uploading = true
         this.uploadProgress = 0

         let maxSize = this.user.maxDiscordMessageSize

         if (this.newSubtitleFile.size >= maxSize) {
            this.$toast.error(this.$t("toasts.fileTooBig", { max: filesize(maxSize) }))
            this.uploading = false
            return
         }
         let file = this.selected[0]
         try {

            let res = await canUpload(file.parent_id)
            if (!res.can_upload) {
               return
            }
            let fileFormList = new FormData()

            let method = file.encryption_method
            let iv = generateIv(method)
            let key = generateKey()
            let encryptedBlob = await encrypt(this.newSubtitleFile, method, key, iv, 0)

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

            let subtitle_data = {
               language: this.newLanguage,
               file_id: file.id,
               size: encryptedBlob.size,
               message_id: uploadResponse.data.id,
               attachment_id: uploadResponse.data.attachments[0].id,
               iv: iv,
               key: key,
               message_author_id: uploadResponse.data.author.id
            }

            let subtitle_res = await addSubtitle(subtitle_data)
            this.$toast.success(this.$t("toasts.subtitleAdded"))
            this.subtitles.push(subtitle_res)
            this.uploading = false
            this.newLanguage = ""
            this.newSubtitleFile = null

         } catch (error) {
            console.log(error)
            if (error.code === "ERR_CANCELED") return
            this.$toast.error(this.$t("toasts.subtitleUploadFailed"))
            this.uploading = false
            this.uploadProgress = 0
         }
      },
      async removeSubtitle(subtitle_id) {
         await removeSubtitle({"subtitle_id": subtitle_id})
         this.subtitles = this.subtitles.filter(subtitle => subtitle.id !== subtitle_id)
         this.$toast.success(this.$t("toasts.subtitleRemoved"))
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
.subtitle-list {
 list-style: none;
 padding: 0;
}

.subtitle-list li {
 display: flex;
 align-items: center;
 justify-content: space-between;
 margin: 0.5em 0;
}

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

.input-group.input {
 background: transparent;
}

.input-group label {
 font-size: 15px;
 color: var(--textSecondary);
}

.file-label {
 margin-top: 2em;
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
