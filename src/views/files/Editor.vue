<template>
  <div id="editor-container">
    <header-bar>
      <action icon="close" :label="$t('buttons.close')" @action="close()"/>
      <title>{{ file?.name }}</title>
      <action
        v-if="perms?.delete && !isInShareContext"
        id="delete-button"
        icon="delete"
        :label="$t('buttons.moveToTrash')"
        @action="moveToTrash"
        show="moveToTrash"
      />
      <action
        v-if="perms?.modify && !isInShareContext"
        id="save-button"
        icon="save"
        :label="$t('buttons.save')"
        @action="save()"
      />

    </header-bar>

    <breadcrumbs :base="'/share/' + token" :folderList="folderList"/>
    <div class="loading delayed" v-if="loading">
      <div class="spinner">
        <div class="bounce1"></div>
        <div class="bounce2"></div>
        <div class="bounce3"></div>
      </div>
    </div>
    <form id="editor"></form>

  </div>
</template>

<script>
import {mapMutations, mapState} from "vuex"
import buttons from "@/utils/buttons"

import {version as ace_version} from "ace-builds"
import ace from "ace-builds/src-min/ace.js"
import modelist from "ace-builds/src-noconflict/ext-modelist"

import HeaderBar from "@/components/header/HeaderBar.vue"
import Action from "@/components/header/Action.vue"
import Breadcrumbs from "@/components/Breadcrumbs.vue"
import {getFile} from "@/api/files.js"
import {fetchURL} from "@/api/utils.js"
import {theme} from "@/utils/constants.js"
import {breadcrumbs} from "@/api/item.js"
import {getShare} from "@/api/share.js"

export default {
  name: "editor",
  components: {
    HeaderBar,
    Action,
    Breadcrumbs,
  },
  props: {
    fileId: String,
    token: String,
    folderId: String,
  },

  data() {
    return {
      file: null,
      res: null,
      editor: null,
      folderList: [],
    }
  },


  computed: {
    ...mapState(["loading", "items", "perms", "currentFolder", "settings", "error"]),

    isInShareContext() {
      return this.token !== undefined
    },
  },


  created() {
    this.fetchData()

    window.addEventListener("keydown", this.keyEvent)
  },
  beforeDestroy() {
    window.removeEventListener("keydown", this.keyEvent)
    this.editor.destroy()
  },
  async mounted() {

  },
  methods: {
    ...mapMutations(["setLoading"]),

    async fetchData() {
      this.setLoading(true)

      // if editor is opened from Share
      if (this.isInShareContext) {
        let res = await getShare(this.token, this.folderId)
        this.shareObj = res
        console.log(res)

        this.$store.commit("setItems", res.share)

        console.log(this.items)
        this.folderList = res.breadcrumbs

        for (let i = 0; i < this.items.length; i++) {
          if (this.items[i].id === this.fileId) {
            this.file = this.items[i]
          }
        }

      }
      // if its opened from Files, hence we know the user
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
          this.$store.commit("addSelected", this.file)

        }
        this.folderList = await breadcrumbs(this.file.parent_id)

      }

      this.$store.commit("addSelected", this.file)


      let res = await fetch(this.file.download_url, {})
      this.raw = await res.text()
      this.$nextTick(() => this.setupEditor())
      this.setLoading(false)
    },
    setupEditor() {
      const fileContent = this.raw || ""
      ace.config.set(
        "basePath",
        `https://cdn.jsdelivr.net/npm/ace-builds@${ace_version}/src-min-noconflict/`
      )

      this.editor = ace.edit("editor", {
        value: fileContent,
        showPrintMargin: false,
        readOnly: false,
        theme: "ace/theme/chrome",
        mode: modelist.getModeForPath(this.file.name).mode,
        wrap: true,

      })
      if (theme === "dark") {
        this.editor.setTheme("ace/theme/twilight")
      }
      //this.editor.session.getUndoManager().markClean()
      console.log(this.editor.session)

    },
    keyEvent(event) {
      if (!event.ctrlKey && !event.metaKey) {
        return
      }

      if (String.fromCharCode(event.which).toLowerCase() !== "s") {
        return
      }

      event.preventDefault()
      this.save()
    },
    async save() {

      const button = "save"

      buttons.loading(button)
      if (!this.editor.session.getUndoManager().isClean()) {
        let content = this.editor.getValue()

        let webhook = this.settings.webhook

        const formData = new FormData()
        const blob = new Blob([content], {type: 'text/plain'})

        formData.append('file', blob, `chunk_${1}`)
        try {
          const response = await fetch(webhook, {
            method: 'POST',
            body: formData
          })

          if (!response.ok) {
            throw new Error(`Error uploading chunk ${1}/${1}: ${response.statusText}`)
          }

          let json = await response.json()

          await fetchURL(`/api/file/create`, {
            method: "PUT",
            body: JSON.stringify(
              {
                "file_id": this.file.id, "fragment_sequence": 1, "total_fragments": 1,
                "fragment_size": blob.size, "message_id": json.id, "attachment_id": json.attachments[0].id
              }
            )
          })

        } finally {
          buttons.done(button)
        }
      }
      this.editor.session.getUndoManager().markClean()
      buttons.success(button)
      let message = this.$t('toasts.fileSaved')
      this.$toast.success(message)

    },
    moveToTrash() {
      this.$store.commit("showHover", {
        prompt: "moveToTrash",
        confirm: () => {
          this.close()
        },
      })

    },
    close() {
      try {
        if (this.isInShareContext) {
          this.$router.push({name: "Share", params: {"token": this.token, "folderId":this.folderId}})
          return
        }
        let uri = {name: `Files`, params: {folderId: this.file.parent_id}}
        if (!this.editor.session.getUndoManager().isClean()) {
          this.$store.commit("showHover", {
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
      catch {
        alert("Error closing properly... report this")
        this.$router.push({name: `Files`, params: {folderId: this.$store.state.user.root}})

      }

    },
  },
}
</script>