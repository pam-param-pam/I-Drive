<template>

  <div id="editor-container" @wheel="handleZoom" @gesturechange.prevent v-touch:zoom="handlePinch">
    <CodeEditor
      v-if="currentLanguage"
      v-model="raw"
      :font-size="fontSize + 'px'"
      :header="true"
      :languages="currentLanguage"
      :line-nums="true"
      :read-only="readOnly"
      :saveFile="!readOnly"
      :themes="[
            ['atom-one-dark', 'Atom One Dark'],
            ['gradient-dark', 'Gradient Dark'],
            ['devibeans', 'Devibeans'],
            ['night-owl', 'Night Owl'],
            ['github-dark', 'Github Dark']
         ]"
      border-radius="0px"
      height="100%"
      padding="20px"
      width="100%"
      @close="onClose()"
      @saveFile="onSave()"
    >
    </CodeEditor>
    <div v-if="loading">
      <h2 class="message delayed editor-loading">
        <div class="spinner">
          <div class="bounce1"></div>
          <div class="bounce2"></div>
          <div class="bounce3"></div>
        </div>
        <span>{{ $t("files.loading") }}</span>
      </h2>
    </div>
  </div>
</template>

<script>
import { editFile, getFile, getFileRawData } from "@/api/files.js"
import { breadcrumbs } from "@/api/item.js"
import { getShare } from "@/api/share.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"

import CodeEditor from "@/components/SimpleCodeEditor/CodeEditor.vue"
import { isMobile } from "@/utils/common.js"
import throttle from "lodash.throttle"
import { encrypt } from "@/utils/encryption.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { canUpload } from "@/api/user.js"
import { generateIv, generateKey, upload } from "@/utils/uploadHelper.js"
import * as CRC32 from "crc-32"
import { encryptionMethod } from "@/utils/constants.js"

export default {
   name: "editor",

   components: {
      CodeEditor
   },

   props: {
      fileId: {
         type: String,
         required: true
      },
      token: {
         type: String
      },
      folderId: {
         type: String
      }
   },

   data() {
      return {
         file: null,
         raw: "",
         editor: null,
         folderList: [],
         currentLanguage: null,
         savingFile: false,
         fontSize: isMobile() ? 10 : 15,

      }
   },

   computed: {
      ...mapState(useMainStore, ["loading", "items", "settings", "error", "user", "error"]),
      ...mapState(useUploadStore, ["webhooks", "attachmentName"]),

      readOnly() {
         return this.isInShareContext || this.error !== null
      },
      isInShareContext() {
         return this.token !== undefined
      },
   },

   created() {
      this.fetchData()
      window.addEventListener("keydown", this.keyEvent)
   },

   beforeUnmount() {
      window.removeEventListener("keydown", this.keyEvent)
   },

   methods: {
      ...mapActions(useMainStore, ["setLoading", "setItems", "addSelected", "showHover", "setLastItem", "setError"]),
      handleZoom(event) {
         if (event.ctrlKey || event.deltaY === 0) {
            event.preventDefault()
            let delta = event.deltaY < 0 ? 1 : -1
            this.fontSize = Math.max(8, Math.min(40, this.fontSize + delta))
         }
      },
      handlePinch(zoomFactor) {
         if (zoomFactor > 1) {
            this.fontSize = Math.min(30, this.fontSize + 2)
         } else if (zoomFactor < 1) {
            this.fontSize = Math.max(5, this.fontSize - 2)
         }
      },
      guessLanguage() {
         let extensionMap = {
            js: "javascript",
            vue: "vue",
            py: "python",
            java: "java",
            cpp: "Cpp",
            cs: "Cs",
            php: "php",
            rb: "ruby",
            ts: "typescript",
            swift: "swift",
            go: "go",
            kt: "kotlin",
            rs: "rust",
            dart: "dart",
            sh: "shell",
            css: "css",
            sql: "sql",
            pl: "perl",
            r: "r",
            scala: "scala",
            lua: "lua",
            m: "matlab",
            json: "json",
            bash: "bash",
            yml: "yaml",
            yaml: "yaml",
            ps1: "powershell",
            txt: "plaintext",
            mk: "makefile",
            nginx: "nginx",
            gradle: "gradle",
            http: "http",
            jl: "julia",
            ex: "elixir",
            exs: "elixir",
            html: "html",
            dockerfile: "dockerfile",
            md: "markdown",
            apache: "apache",
            ino: "arduino",
            xml: "xml"
         }
         let ext = this.file.name.split(".").pop().toLowerCase()
         let lang = extensionMap[ext] || "plaintext"
         return [[lang, lang]]
      },

      async fetchData() {
         this.setLoading(true)

         // if editor is opened from Share
         if (this.isInShareContext) {
            let res = await getShare(this.token, this.folderId)
            this.shareObj = res
            this.setItems(res.share)
            this.folderList = res.breadcrumbs

            for (let i = 0; i < this.items.length; i++) {
               if (this.items[i].id === this.fileId) {
                  this.file = this.items[i]
               }
            }
         }
         // if It's opened from Files, hence we know the user
         else {
            if (this.items) {
               for (let i = 0; i < this.items.length; i++) {
                  if (this.items[i].id === this.fileId) {
                     this.file = this.items[i]
                  }
               }
            }
            if (!this.file) {
               this.file = await getFile(this.fileId)
            }
            this.folderList = await breadcrumbs(this.file.parent_id)
         }

         this.addSelected(this.file)

         try {
            this.raw = await getFileRawData(this.file.download_url)
            this.setLastItem(this.file)
         } catch (error) {
            console.log(error)
            this.setError(error)
            this.raw = "Failed to load file. Status code: " + this.error.response.status
         } finally {
            this.copyRaw = this.raw
            this.currentLanguage = this.guessLanguage()
            this.setLoading(false)
         }
      },

      keyEvent(event) {
         if (!event.ctrlKey && !event.metaKey) {
            return
         }
         if (String.fromCharCode(event.which).toLowerCase() !== "s") {
            return
         }
         event.preventDefault()
         this.onSave()
      },

      onSave: throttle(async function(event) {
         if (this.savingFile) return
         try {
            this.savingFile = true
            document.querySelector("#save-button").classList.add("loading")

            let res = await canUpload(this.file.parent_id)
            if (!res.can_upload) {
               return
            }
            if (this.raw !== this.copyRaw) {
               let method = this.file.encryption_method
               let iv
               let key
               if (method !== encryptionMethod.NotEncrypted) {
                  iv = generateIv(method)
                  key = generateKey(method)
               }
               let formData = new FormData()
               let blob = new Blob([this.raw])
               let encryptedBlob = await encrypt(blob, method, key, iv, 0)

               formData.append("file", encryptedBlob, this.attachmentName)

               let crc = CRC32.buf(new Uint8Array(await blob.arrayBuffer()), 0)
               let uploadResponse = await upload(formData, {})

               let file_data = {
                  file_id: this.file.id,
                  offset: 0,
                  fragment_size: encryptedBlob.size,
                  message_id: uploadResponse.data.id,
                  attachment_id: uploadResponse.data.attachments[0].id,
                  message_author_id: uploadResponse.data.author.id,
                  iv: iv,
                  key: key,
                  crc: crc
               }

               await editFile(file_data)
               this.copyRaw = this.raw
            }
            document.querySelector("#save-button").classList.remove("loading")

            document.querySelector("#save-button").classList.add("success")
            setTimeout(() => {
               document.querySelector("#save-button").classList.remove("success")
            }, 2500)
            let message = this.$t("toasts.fileSaved")
            this.$toast.success(message)

         } catch (e) {
            document.querySelector("#save-button").classList.remove("loading")
            console.error(e)
            this.$toast.error(e.toString())
         } finally {
            this.savingFile = false
         }
      }, 1000),

      onClose() {
         try {
            if (this.isInShareContext) {
               this.$router.push({
                  name: "Share",
                  params: { token: this.token, folderId: this.folderId }
               })
               return
            }
            let uri = { name: `Files`, params: { folderId: this.file.parent_id } }
            if (this.raw !== this.copyRaw) {
               this.showHover({
                  prompt: "discardEditorChanges",
                  confirm: () => {
                     this.$router.push(uri)
                  }
               })
               return
            }

            this.$router.push(uri)
         } catch (e) {
            // catch every error so user can always close...
            console.error(e)
            this.$router.push({ name: `Files`, params: { folderId: this.user.root } })
         }
      }
   }
}
</script>

<style>
.editor-loading {
 width: 103%;
 padding-top: 3em;
}
</style>
