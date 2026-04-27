<template>
   <div id="editor-container">
      <!-- preview container -->
      <div class="loading delayed" v-show="loading">
         <div class="spinner">
            <div class="bounce1"></div>
            <div class="bounce2"></div>
            <div class="bounce3"></div>
         </div>
      </div>

      <div class="editor-header">
         <div>
            <!-- theme selector -->
            <select v-if="!isPreview" v-model="selectedTheme" @change="applyTheme">
               <option
                  v-for="theme in currentThemes"
                  :key="theme.value"
                  :value="theme.value"
               >
                  {{ theme.name }}
               </option>
            </select>

            <!-- font controls -->
            <action v-if="!isPreview" icon="remove" @action="decreaseFontSize" />
            <span v-if="!isPreview" class="font-size">{{ fontSize }}</span>
            <action v-if="!isPreview" icon="add" @action="increaseFontSize" />
            <action
               v-if="isMarkdownFile"
               icon="preview"
               @action="preview()"
            />
            <action
               buttonId="copy"
               icon="file_copy"
               @action="copy()"
            />
            <action
               v-if="!readonly"
               buttonId="save"
               icon="save"
               @action="save()"
            />
         </div>
      </div>

      <div
         v-show="isPreview && isMarkdownFile"
         id="preview-container"
         class="md_preview"
         v-html="previewContent"
      ></div>
      <form v-show="!isPreview || !isMarkdownFile" id="editor"></form>
   </div>
</template>

<script>
import ace, { version as ace_version } from "ace-builds"
import "ace-builds/src-noconflict/ext-language_tools"
import DOMPurify from "dompurify"
import modelist from "ace-builds/src-noconflict/ext-modelist"
import Action from "@/components/header/Action.vue"
import HeaderBar from "@/components/header/HeaderBar.vue"
import { marked } from "marked"
import markedKatex from "marked-katex-extension"
import { editFile, getFileRawData } from "@/api/files.js"
import { mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import buttons from "@/utils/buttons.js"
import throttle from "lodash.throttle"
import { canUpload } from "@/api/user.js"
import { encryptionMethod, PreviewEvent } from "@/utils/constants.js"
import { generateIv, generateKey, upload } from "@/upload/utils/uploadHelper.js"
import { encrypt } from "@/upload/utils/encryption.js"
import { buf as crc32buf } from "crc-32"

export default {
   components: {
      Action,
      HeaderBar
   },

   props: ["file", "readonly"],
   emits: ["previewEvent", "error"],

   data() {
      return {
         loading: false,
         editor: null,
         fontSize: parseInt(localStorage.getItem("editorFontSize") || "14"),
         isPreview: false,
         previewContent: "",
         originalContent: null,
         savingFile: false,
         selectedTheme: null,
         lightThemes: [
            { value: "ace/theme/chrome", name: "Chrome" },
            { value: "ace/theme/github", name: "Github Light" }
         ],
         darkThemes: [
            { value: "ace/theme/one_dark", name: "One Dark" },
            { value: "ace/theme/github_dark", name: "GitHub Dark" },
            { value: "ace/theme/tomorrow_night", name: "Tomorrow Night" },
            { value: "ace/theme/dracula", name: "Dracula" },
            { value: "ace/theme/terminal", name: "Terminal" }
         ]
      }
   },
   watch: {
      isPreview: "updatePreview",
      file: "fetchData"
   },
   computed: {
      ...mapState(useMainStore, ["settings"]),
      isMarkdownFile() {
         return (this.file.name.endsWith(".md") || this.file.name.endsWith(".markdown"))
      },
      currentThemes() {
         return this.settings.theme === "dark" ? this.darkThemes : this.lightThemes
      },
      defaultTheme() {
         return this.currentThemes[0].value
      },
      currentTheme() {
         let stored = localStorage.getItem(this.storageKey)
         let exists = this.currentThemes.some(t => t.value === stored)
         return exists ? stored : this.defaultTheme
      },
      storageKey() {
         return this.settings.theme === "dark" ? "editorDarkTheme" : "editorLightTheme"
      }
   },

   created() {
      this.selectedTheme = this.currentTheme
      marked.use(
         markedKatex({
            output: "mathml",
            throwOnError: false
         })
      )
   },

   async mounted() {
      window.addEventListener("keydown", this.keyEvent)

      await this.fetchData()
   },

   beforeUnmount() {
      window.removeEventListener("keydown", this.keyEvent)
      this.editor?.destroy()
   },

   methods: {
      async fetchData() {
         this.editor?.destroy()
         this.setLoading(true)
         try {
            let fileContent = await getFileRawData(this.file.download_url, { responseType: "text" })
            this.originalContent = fileContent
            this.initEditor(fileContent)
         } catch (error) {
            console.log(error)
            this.$emit("error", error)
         } finally {
            this.setLoading(false)
         }
      },
      async updatePreview() {
         if (this.isMarkdownFile && this.isPreview) {
            try {
               const value = this.editor?.getValue() || ""
               this.previewContent = DOMPurify.sanitize(await marked(value))
            } catch (e) {
               console.error(e)
               this.previewContent = ""
            }
         }
      },
      keyEvent(event) {
         if (event.ctrlKey && event.key === "s") {
            event.preventDefault()
            this.save()
         }
      },
      setLoading(value) {
         this.loading = value
      },
      applyTheme() {
         localStorage.setItem(this.storageKey, this.selectedTheme)
         this.editor?.setTheme(this.selectedTheme)
      },
      initEditor(fileContent) {
         ace.config.set("basePath", `https://cdn.jsdelivr.net/npm/ace-builds@${ace_version}/src-min-noconflict/`)

         const mode = modelist.getModeForPath(this.file.name).mode

         this.editor = ace.edit("editor", {
            value: fileContent,
            showPrintMargin: false,
            readOnly: this.readonly,
            mode: mode,
            wrap: true,
            enableBasicAutocompletion: true,
            enableLiveAutocompletion: true,
            enableSnippets: true
         })
         this.editor.container.style.visibility = "hidden"
         this.editor.setTheme(this.selectedTheme, () => {
            this.editor.container.style.visibility = "visible"
            this.editor.resize()
         })
         this.editor.setFontSize(this.fontSize)
         this.editor.focus()

         let undoManager = this.editor.session.getUndoManager()
         undoManager.markClean()
         this.editor.session.on("change", () => {
            const isClean = this.editor.getValue() === this.originalContent
            this.$emit("previewEvent", { type: PreviewEvent.EDITOR_CLEAN_CHANGE, payload: { is_clean: isClean } })
         })

         this.setLoading(false)
      },

      save: throttle(async function(event) {
         if (this.savingFile) return
         try {
            this.savingFile = true
            buttons.loading("save")

            let res = await canUpload(this.file.parent_id)
            if (!res.can_upload) return
            let raw = this.editor.getValue()

            if (raw !== this.originalContent) {

               if (!raw) {
                  await editFile(this.file.id, { "file_data": null })
                  this.onSuccessfulSave()
                  return
               }

               let method = this.file.encryption_method
               let iv
               let key
               if (method !== encryptionMethod.NotEncrypted) {
                  iv = generateIv(method)
                  key = generateKey(method)
               }
               let formData = new FormData()
               let blob = new Blob([String(raw)])
               let encryptedBlob = await encrypt(blob, method, key, iv, 0)

               formData.append("file", encryptedBlob, this.attachmentName)

               let crc = crc32buf(new Uint8Array(await blob.arrayBuffer()), 0) || 0
               crc = crc >>> 0
               let uploadResponse = await upload(formData, {})

               let attachment_data = {
                  offset: 0,
                  fragment_sequence: 1,
                  fragment_size: encryptedBlob.size,
                  channel_id: uploadResponse.data.channel_id,
                  message_id: uploadResponse.data.id,
                  attachment_id: uploadResponse.data.attachments[0].id,
                  message_author_id: uploadResponse.data.author.id,
                  crc: crc
               }

               let file_data = {
                  iv: iv,
                  key: key,
                  crc: crc,
                  attachment: attachment_data
               }
               await editFile(this.file.id, { "file_data": file_data })
            }
            this.onSuccessfulSave()

         } catch (e) {
            console.error(e)
            buttons.done("save")
            this.$toast.error(e.toString())
         } finally {
            this.savingFile = false
         }
      }, 1000),
      onSuccessfulSave() {
         buttons.done("save")
         buttons.success("save")
         this.originalContent = this.editor.getValue()
         this.$emit("previewEvent", { type: PreviewEvent.EDITOR_CLEAN_CHANGE, payload: { is_clean: true } })
         let message = this.$t("toasts.fileSaved")
         this.$toast.success(message)
      },

      increaseFontSize() {
         this.fontSize += 1
         this.editor?.setFontSize(this.fontSize)
         localStorage.setItem("editorFontSize", this.fontSize.toString())
      },

      decreaseFontSize() {
         if (this.fontSize > 1) {
            this.fontSize -= 1
            this.editor?.setFontSize(this.fontSize)
            localStorage.setItem("editorFontSize", this.fontSize.toString())
         }
      },
      copy() {
         navigator.clipboard.writeText(this.editor.getValue())
         buttons.success("copy")
      },

      preview() {
         this.isPreview = !this.isPreview
      }
   }

}
</script>

<style scoped>

.editor-header {
  display: flex;
  justify-content: flex-end;
}

.editor-header > div > button:hover:not(:disabled) {
  opacity: 1;
}

.editor-header > div > button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.editor-header > div > button > span > i {
  font-size: 1.2rem;
}

.md_preview {
  padding: 1rem;
  border: 1px solid #000;
  font-size: 20px;
  line-height: 1.2;
}

#preview-container {
  text-align: left !important;
  overflow: auto;
  flex: 1;
}


#editor-container {
  display: flex;
  flex-direction: column;
  background-color: var(--background);
  height: 100%;
  width: 100%;
  overflow: hidden;
}

#editor-container .bar {
  background: var(--surfacePrimary);
}

#editor-container #editor {
  flex: 1;
}

.font-size {
  min-width: 24px;
  text-align: center;
  font-size: 12px;
  opacity: 0.7;
}

.editor-header select {
  border-radius: 5px;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;

  background-color: var(--surfacePrimary);
  color: var(--textPrimary);

  border: 1px solid rgba(255, 255, 255, 0.15);

  padding: 4px 28px 4px 8px;
  font-size: 12px;

  cursor: pointer;
  outline: none;

  transition: border-color 0.2s, background-color 0.2s;
}
</style>