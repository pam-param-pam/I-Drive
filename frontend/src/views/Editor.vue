<template>

  <div id="editor-container">

    <CodeEditor
      v-if="currentlanguage"
      v-model="raw"
      :line-nums="true"
      width="100%"
      height="100%"
      border-radius="0px"
      padding="20px"
      :saveFile="!isInShareContext"
      :header="true"
      :font-size="fontSize"
      :isSaveBtnLoading="isSaveBtnLoading"
      :languages="currentlanguage"
      @close="onClose()"
      @saveFile="onSave()"
      :read-only="isInShareContext"
      :themes='[["atom-one-dark", "Atom One Dark"], ["gradient-dark", "Gradient Dark"], ["devibeans", "Devibeans"], ["night-owl", "Night Owl"], ["github-dark", "Github Dark"]]'
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
import {editFile, getEncryptionSecrets, getFile} from "@/api/files.js"
import {breadcrumbs} from "@/api/item.js"
import {getShare} from "@/api/share.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"

import CodeEditor from "@/components/SimpleCodeEditor/CodeEditor.vue"
import {discord_instance} from "@/utils/networker.js";
import {isMobile} from "@/utils/common.js";
import throttle from "lodash.throttle"


export default {
   name: "editor",
   components: {
      CodeEditor,

   },
   props: {
      fileId: {
         type: String,
         required: true,
      },
      token: {
         type: String,
      },
      folderId: {
         type: String,
      },

   },

   data() {
      return {
         file: null,
         res: null,
         raw: '',
         editor: null,
         folderList: [],
         isSaveBtnLoading: false,
         currentlanguage: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["loading", "items", "settings", "error", "user"]),

      isInShareContext() {
         return this.token !== undefined
      },
      fontSize() {
         if (isMobile()) return "10px"
         else return "15px"
      },


   },

   created() {

      this.fetchData()
      window.addEventListener("keydown", this.keyEvent)
   },
   beforeUnmount() {
      window.removeEventListener("keydown", this.keyEvent)
   },
   async mounted() {
      console.log("mounted")

   },
   methods: {
      ...mapActions(useMainStore, ["setLoading", "setItems", "addSelected", "showHover", "setLastItem"]),
      guessLanguage() {
         console.log("guessLanguage")

         let extensionMap = {
            'js': 'javascript',
            'vue': "vue",
            'py': 'python',
            'java': 'java',
            'cpp': 'Cpp',
            'cs': 'Cs',
            'php': 'php',
            'rb': 'ruby',
            'ts': 'typescript',
            'swift': 'swift',
            'go': 'go',
            'kt': 'kotlin',
            'rs': 'rust',
            'dart': 'dart',
            'sh': 'shell',
            'css': 'css',
            'sql': 'sql',
            'pl': 'perl',
            'r': 'r',
            'scala': 'scala',
            'lua': 'lua',
            'm': 'matlab',
            'json': 'json',
            'bash': 'bash',
            'yml': 'yaml',
            'yaml': 'yaml',
            'ps1': 'powershell',
            'txt': 'plaintext',
            'mk': 'makefile',
            'nginx': 'nginx',
            'gradle': 'gradle',
            'http': 'http',
            'jl': 'julia',
            'ex': 'elixir',
            'exs': 'elixir',
            'html': 'html',
            'dockerfile': 'dockerfile',
            'md': 'markdown',
            'apache': 'apache',
            'ino': 'arduino',
            'xml': 'xml',
         };
         let ext = this.file.name.split('.').pop().toLowerCase()
         let lang = extensionMap[ext] || 'plaintext'
         return [[lang, lang]]
      },
      async fetchData() {
         this.setLoading(true)

         // if editor is opened from Share
         if (this.isInShareContext) {
            let res = await getShare(this.token, this.folderId)
            this.shareObj = res
            console.log(res)

            this.setItems(res.share)
            console.log(this.items)
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
               console.log("FILEID: " + this.fileId)
               this.file = await getFile(this.fileId)
            }
            this.folderList = await breadcrumbs(this.file.parent_id)

         }

         this.addSelected(this.file)

         console.log("STARTED FETCHING")
         //todo show a progress bar
         let res = await fetch(this.file.download_url, {})
         console.log("STOPPED FETCHING")
         this.setLoading(false)

         // this.raw = "aaaa"
         this.raw = await res.text()
         this.copyRaw = this.raw

         this.currentlanguage = this.guessLanguage()

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

       onSave: throttle(async function (event) {
         document.querySelector('#save-button').classList.add('loading'); // Set to loading

         if (this.raw !== this.copyRaw) {
            // this.isSaveBtnLoading = true
            let webhook = this.settings.webhook

            let formData = new FormData()
            let content = this.raw

            if (this.file.is_encrypted) {
               let secrets = await getEncryptionSecrets(this.file.id)
               // Ensure content is a Blob before encrypting
               if (typeof content === 'string') {
                  content = new Blob([content], {type: 'text/plain'})
               }
               // content = await encrypt(secrets.key, secrets.iv, content) //todo fix encryptiopn

            }
            let blob = new Blob([content])

            formData.append('file', blob, `chunk_${1}`)

            let response = await discord_instance.post(webhook, formData, {
               headers: {
                  'Content-Type': 'multipart/form-data'
               },
            })

            let json = response.data
            let file_data = {
               "file_id": this.file.id, "fragment_sequence": 1, "total_fragments": 1,
               "fragment_size": blob.size, "message_id": json.id, "attachment_id": json.attachments[0].id
            }


            await editFile(file_data)
            this.copyRaw = this.raw
         }
         document.querySelector('#save-button').classList.remove('loading'); // Remove loading

         document.querySelector('#save-button').classList.add('success'); // Set to success
         setTimeout(() => {
            document.querySelector('#save-button').classList.remove('success'); // Remove loading
         }, 2500)
         let message = this.$t('toasts.fileSaved')
         this.$toast.success(message)

       }, 1000),

      onClose() {
         this.setLastItem(this.file)

         try {
            if (this.isInShareContext) {
               this.$router.push({name: "Share", params: {"token": this.token, "folderId": this.folderId}})
               return
            }
            let uri = {name: `Files`, params: {folderId: this.file.parent_id}}
            if (this.raw !== this.copyRaw) {
               this.showHover({
                  prompt: "discardEditorChanges",
                  confirm: () => {
                     this.$router.push(uri)

                  },
               })
               return
            }

            this.$router.push(uri)
         }
            // catch every error so user can always close...
         catch (e) {
            console.error(e)
            this.$router.push({name: `Files`, params: {folderId: this.user.root}})

         }


      },

   }
}
</script>

<style>
.editor-loading {
 width: 103%;
 padding-top: 3em;
}
</style>