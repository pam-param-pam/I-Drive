<template>
   <div class="card floating subtitle-manager">
      <div class="card-title">
         <h2>{{ $t("prompts.manageSubtitles") }}</h2>
      </div>

      <div class="card-content">
         <p v-if="subtitles.length !== 0">{{ $t("prompts.existingSubtitles") }}: </p>
         <ul class="subtitle-list">
            <li v-for="sub in subtitles" :key="sub.id">
               <!-- DISPLAY MODE -->
               <label
                  v-if="editingId !== sub.id"
                  class="subtitle-lang"
               >
                  {{ sub.language }}
               </label>

               <!-- EDIT MODE -->
               <input
                  v-else
                  class="subtitle-lang-input"
                  v-model.trim="editingValue"
                  @blur="commitEdit(sub)"
                  @keydown.enter.prevent="commitEdit(sub)"
               />

               <div class="subtitle-actions">
                  <button
                     class="action"
                     @click="startEdit(sub)"
                     :disabled="editingId === sub.id"
                  >
                     <i class="material-icons">edit</i>
                  </button>

                  <button class="action remove" @click="removeSubtitle(sub.id)">
                     <i class="material-icons">delete</i>
                  </button>
               </div>
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
            <SmartFileInput
               ref="subtitleFileInput"
               accept=".vtt,.srt"
               :label="$t('buttons.addSubtitleFile')"
               @file-selected="onSubtitleInput"
            />
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
                  <input type="checkbox" v-model="subtitleStyle.default" />
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
            @click="submit"
         >
            {{ $t("buttons.save") }}
         </button>
      </div>
   </div>
</template>

<script>
import { addSubtitle, getSubtitles, deleteSubtitle, renameSubtitle } from "@/api/files.js"
import { filesize } from "@/utils/index.js"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { canUpload } from "@/api/user.js"
import { generateIv, generateKey, upload } from "@/upload/utils/uploadHelper.js"

import axios from "axios"
import ProgressBar from "@/components/upload/UploadProgressBar.vue"
import { useUploadStore } from "@/stores/uploadStore.js"
import { encrypt } from "@/upload/utils/encryption.js"
import { detectExtension } from "@/utils/common.js"
import { capitalize } from "vue"
import { buildVttFromSrt } from "@/utils/subtitleUtlis.js"
import SmartFileInput from "@/components/SmartFileInput.vue"

export default {
   name: "manage-subtitles",
   components: { SmartFileInput, ProgressBar },
   data() {
      return {
         subtitles: [],
         newSubtitleFile: null,
         newLanguage: "",
         cancelTokenSource: null,
         uploadProgress: 0,
         uploading: false,
         isExpanded: false,
         editingId: null,
         editingValue: "",
         subtitleStyle: {
            fontSize: 50,
            color: "#fbeda5",
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            textShadow: "2px 2px 4px #000000",
            default: true
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

      let savedStyle = localStorage.getItem("subtitleStyle")
      if (savedStyle) {
         try {
            this.subtitleStyle = JSON.parse(savedStyle)
         } catch (e) {
            console.warn("Failed to parse subtitleStyle from localStorage")
         }
      }
   },
   watch: {
      subtitleStyle: {
         handler(newValue) {
            localStorage.setItem("subtitleStyle", JSON.stringify(newValue))
         },
         deep: true
      }
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"]),
      startEdit(sub) {
         this.editingId = sub.id
         this.editingValue = sub.language

         this.$nextTick(() => {
            const input = document.querySelector(".subtitle-lang-input")
            input?.focus()
         })
      },

      async commitEdit(sub) {
         if (this.editingId !== sub.id) return

         const newLanguage = this.editingValue.trim()

         // cancel if unchanged or empty
         if (!newLanguage || newLanguage === sub.language) {
            this.resetEdit()
            return
         }

         try {
            await renameSubtitle(this.selected[0].id, sub.id, newLanguage)
            sub.language = newLanguage
            this.$toast.success(this.$t("toasts.subtitleRenamed"))
         } catch (e) {
            console.error(e)
            this.$toast.error(this.$t("toasts.subtitleRenameFailed"))
         } finally {
            this.resetEdit()
         }
      },

      resetEdit() {
         this.editingId = null
         this.editingValue = ""
      },

      async onSubtitleInput(file) {
         if (!this.validateSubtitleFile(file)) return

         let processedFile = await this.prepareSubtitleFile(file)
         this.newSubtitleFile = processedFile
         if (!this.newLanguage.trim()) {
            this.newLanguage = this.extractLanguageName(processedFile.name)
         }
      },

      validateSubtitleFile(file) {
         if (!file) return false
         let valid = file.name.endsWith(".vtt") || file.name.endsWith(".srt")
         if (!valid) {
            this.$toast.error(this.$t("toasts.invalidSubtitleFormat"))
            return false
         }

         if (file.size >= this.user.maxDiscordMessageSize) {
            this.$toast.error(this.$t("toasts.fileTooBig", { max: filesize(this.user.maxDiscordMessageSize) }))
            return false
         }
         return true
      },

      async prepareSubtitleFile(file) {
         if (!file.name.endsWith(".srt")) return file
         let text = await file.text()
         let vttText = buildVttFromSrt(text)
         return new File([vttText], file.name)
      },

      extractLanguageName(filename) {
         const ext = detectExtension(filename)
         return capitalize(filename.replace(ext, ""))
      },

      async submit() {
         if (!this.canSubmit || this.uploading) return

         this.uploading = true
         this.uploadProgress = 0

         try {
            const file = this.selected[0]

            let res = await canUpload(file.parent_id)
            if (!res.can_upload) return

            const encrypted = await this.encryptSubtitleFile(file.encryption_method)
            const uploadResponse = await this.uploadEncryptedSubtitle(encrypted)
            const subtitleData = this.buildSubtitleReq(file, encrypted, uploadResponse)
            const subtitleRes = await this.saveSubtitle(file.id, subtitleData)

            this.onSubtitleUploadSuccess(subtitleRes)
         } catch (error) {
            this.handleSubtitleUploadError(error)
         } finally {
            this.uploading = false
            this.uploadProgress = 0
         }
      },

      async encryptSubtitleFile(method) {
         const iv = generateIv(method)
         const key = generateKey(method)
         const encryptedBlob = await encrypt(this.newSubtitleFile, method, key, iv, 0)
         return { iv, key, blob: encryptedBlob }
      },

      async uploadEncryptedSubtitle({ blob }) {
         this.cancelTokenSource = axios.CancelToken.source()
         const form = new FormData()
         form.append("file", blob, this.attachmentName)

         const config = {
            onUploadProgress: this.trackUploadProgress,
            cancelToken: this.cancelTokenSource.token
         }

         return await upload(form, config)
      },

      trackUploadProgress(progressEvent) {
         if (progressEvent.total) {
            this.uploadProgress = Math.round((progressEvent.loaded / progressEvent.total) * 100)
         }
      },

      buildSubtitleReq(file, { iv, key, blob }, uploadResponse) {
         let data = uploadResponse.data
         return {
            language: this.newLanguage,
            size: blob.size,
            channel_id: data.channel_id,
            message_id: data.id,
            attachment_id: data.attachments[0].id,
            is_forced: false,
            iv: iv,
            key: key,
            message_author_id: data.author.id
         }
      },

      async saveSubtitle(fileId, subtitleData) {
         return await addSubtitle(fileId, subtitleData)
      },

      onSubtitleUploadSuccess(subtitleRes) {
         this.subtitles = [...this.subtitles, subtitleRes]
         this.$refs.subtitleFileInput.reset()
         this.$toast.success(this.$t("toasts.subtitleAdded"))
         this.newLanguage = ""
      },

      handleSubtitleUploadError(error) {
         if (error.code === "ERR_CANCELED") return
         console.error(error)
         this.$toast.error(this.$t("toasts.subtitleUploadFailed"))
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

.advanced-settings .input-color input {
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

.subtitle-list li {
 display: flex;
 align-items: center;
}

.subtitle-lang {
 margin-right: auto;
}

.subtitle-actions {
 display: flex;
 gap: 0.5em;
}

.subtitle-lang-input {
 font-size: inherit;
 background: var(--surfaceSecondary);
 color: var(--textPrimary);
 border: 1px solid var(--divider);
 border-radius: 4px;
 padding: 0.2em 0.4em;
}
</style>
