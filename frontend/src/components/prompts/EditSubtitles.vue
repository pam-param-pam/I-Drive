<template>
  <div class="card floating subtitle-manager">
    <div class="card-title">
      <h2>{{ $t("prompts.manageSubtitles") }}</h2>
    </div>

    <div class="card-content">
      <p v-if="subtitles.length !== 0">{{ $t("prompts.existingSubtitles") }}: </p>
      <ul class="subtitle-list">
        <li v-for="(sub) in subtitles" :key="sub.id">
          <label class="subtitle-lang">{{ sub.language }}</label>
          <button class="action remove" @click="removeSubtitle(sub.id)">
            <i class="material-icons">delete</i>
          </button>
        </li>
      </ul>

      <hr v-if="subtitles.length !== 0" />

      <p><strong>{{ $t("prompts.addSubtitle") }}</strong></p>
      <div class="input-group input">
        <label for="langInput">{{ $t("prompts.subtitleLanguage") }}</label>
        <input
          id="langInput"
          v-model.trim="newLanguage"
          placeholder="English"
          class="input input--block"
        />
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

      <div v-if="uploading" class="prompts-progress-bar-wrapper">
        <ProgressBar :progress="uploadProgress" />
        <span><b>{{ uploadProgress }}%</b></span>
      </div>

      <!-- Expandable section -->
      <div class="expandable-section">
        <div class="expandable-header" @click="isExpanded = !isExpanded">
          <strong>{{ $t("prompts.advanced") }}</strong>
          <i :class="{ expanded: isExpanded }" class="material-icons expand-icon">
            keyboard_arrow_down
          </i>
        </div>

        <div v-if="isExpanded" class="expandable-content  advanced-settings">

          <div class="input-group">
            <label>Font Size (px)</label>
            <input type="number" v-model.number="subtitleStyle.fontSize" min="10" />
          </div>
          <div class="input-group input-color">
            <label>Font Color</label>
            <input type="color" v-model="subtitleStyle.color" />
          </div>
          <div class="input-group input-color">
            <label>Background Color</label>
            <input type="color" v-model="subtitleStyle.backgroundColor" />
          </div>
          <div class="input-group">
            <label>Text Shadow</label>
            <input type="text" v-model="subtitleStyle.textShadow" placeholder="e.g. 2px 2px 4px #000000" />
          </div>
          <div class="input-group">
            <label>Default</label>
            <input type="checkbox" v-model="subtitleStyle.default"/>
          </div>
        </div>
      </div>
    </div>
    <div class="card-action">
      <button class="button button--flat button--grey" @click="cancel">
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
import { addSubtitle, getSubtitles, deleteSubtitle } from "@/api/files.js"
import { filesize } from "@/utils/index.js"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { canUpload } from "@/api/user.js"
import { generateIv, generateKey, upload } from "@/upload/uploadHelper.js"

import { encrypt } from "@/utils/encryption.js"
import axios from "axios"
import ProgressBar from "@/components/upload/UploadProgressBar.vue"
import { useUploadStore } from "@/stores/uploadStore.js"

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
         uploading: false,
         isExpanded: false,
         subtitleStyle: {
            fontSize: 50,
            color: "#fbeda5",
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            textShadow: "2px 2px 4px #000000",
            default: true,
         }
      }
   },
   computed: {
      ...mapState(useMainStore, ["user", "selected"]),
      ...mapState(useUploadStore, ["attachmentName"]),
      canSubmit() {
         return this.newSubtitleFile && this.newLanguage.length > 0
      }
   },
   async mounted() {
      this.subtitles = await getSubtitles(this.selected[0]?.id)

      let savedStyle = localStorage.getItem('subtitleStyle');
      if (savedStyle) {
         try {
            this.subtitleStyle = JSON.parse(savedStyle);
         } catch (e) {
            console.warn("Failed to parse subtitleStyle from localStorage");
         }
      }
   },
   watch: {
      subtitleStyle: {
         handler(newValue) {
            localStorage.setItem('subtitleStyle', JSON.stringify(newValue))
         },
         deep: true
      }
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
         let maxSize = this.user.maxDiscordMessageSize
         if (file.size >= maxSize) {
            this.$toast.error(this.$t("toasts.fileTooBig", { max: filesize(maxSize) }))
            return
         }

         this.newSubtitleFile = file
      },

      async addSubtitle() {
         if (!this.canSubmit || this.uploading) return

         try {
            this.uploading = true
            this.uploadProgress = 0
            let file = this.selected[0]

            let allowed = await canUpload(file.parent_id)
            if (!allowed) return

            let method = file.encryption_method
            let iv = generateIv(method)
            let key = generateKey(method)
            let encryptedBlob = await encrypt(this.newSubtitleFile, method, key, iv, 0)

            this.cancelTokenSource = axios.CancelToken.source()
            let form = new FormData()
            form.append("file", encryptedBlob, this.attachmentName)

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

            let uploadResponse = await upload(form, config)

            let subtitle_data = {
               language: this.newLanguage,
               size: encryptedBlob.size,
               channel_id: uploadResponse.data.channel_id,
               message_id: uploadResponse.data.id,
               attachment_id: uploadResponse.data.attachments[0].id,
               iv: iv,
               key: key,
               message_author_id: uploadResponse.data.author.id
            }

            let subtitle_res = await addSubtitle(file.id, subtitle_data)

            this.$toast.success(this.$t("toasts.subtitleAdded"))
            this.subtitles.push(subtitle_res)
            this.newLanguage = ""
            this.newSubtitleFile = null

         } catch (error) {
            if (error.code === "ERR_CANCELED") return
            this.$toast.error(this.$t("toasts.subtitleUploadFailed"))
         } finally {
            this.uploading = false
            this.uploadProgress = 0
         }
      },

      async removeSubtitle(subtitle_id) {
         await deleteSubtitle(this.selected[0].id, subtitle_id)
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
 margin-top: 2em;
}

.input-group.input {
 background: transparent;
}

.input-group label {
 font-size: 15px;
 color: var(--textSecondary);
}

.prompts-progress-bar-wrapper {
 display: flex;
 align-items: center;
 gap: 1em;
 margin-top: 1em;
}

.advanced-settings {
 margin-top: 1em;
 padding: 1em;
 background: var(--surfacePrimary);
 border: 1px solid var(--divider);
 border-radius: 8px;
}

.advanced-settings .input-group {
 margin-bottom: 1em;
}

.advanced-settings .input-color input{
 padding: 0.20em 0.20em !important;
 height: 25px;
}


.advanced-settings input,
.advanced-settings select {
 margin-top: 0.5em;
 margin-left: 0.5em;
 padding: 0.5em 0.5em;
 border: 1px solid var(--divider);
 border-radius: 6px;
 background-color: var(--surfaceSecondary);
 color: var(--textPrimary);
 font-size: 14px;
 box-sizing: border-box;
}

.subtitle-lang {
 color: var(--textSecondary);
 padding-left: 0.5em;
}
</style>
