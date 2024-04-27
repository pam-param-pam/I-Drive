<template>
  <div id="editor-container">
    <header-bar>
      <action icon="close" :label="$t('buttons.close')" @action="close()"/>
      <title>{{ file?.name }}</title>

      <action
        v-if="perms.modify"
        id="save-button"
        icon="save"
        :label="$t('buttons.save')"
        @action="save()"
      />
    </header-bar>

    <breadcrumbs base="/files/"/>
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
import {mapMutations, mapState} from "vuex";
import {files as api} from "@/api";
import buttons from "@/utils/buttons";

import {version as ace_version} from "ace-builds";
import ace from "ace-builds/src-min/ace.js";
import modelist from "ace-builds/src-noconflict/ext-modelist";

import HeaderBar from "@/components/header/HeaderBar.vue";
import Action from "@/components/header/Action.vue";
import Breadcrumbs from "@/components/Breadcrumbs.vue";
import {getFile} from "@/api/files.js";
import store from "@/store/index.js";
import {fetchURL} from "@/api/utils.js";

export default {
  name: "editor",
  components: {
    HeaderBar,
    Action,
    Breadcrumbs,
  },
  computed: {
    ...mapState(["loading", "items", "perms", "currentFolder"]),
  },
  data: function () {
    return {
      file: null,
      res: null,
      editor: null,
    };
  },

  created() {
    console.log("aaaaaaaaaa");
    this.fetchData();

    window.addEventListener("keydown", this.keyEvent);
  },
  beforeDestroy() {
    window.removeEventListener("keydown", this.keyEvent);
    this.editor.destroy();
  },
  async mounted() {

  },
  methods: {
    ...mapMutations(["setLoading"]),

    async fetchData() {
      let fileId = this.$route.params.fileId;
      this.setLoading(true);

      if (this.items) {
        for (let i = 0; i < this.items.length; i++) {
          if (this.items[i].id === fileId) {
            this.file = this.items[i];
          }
        }
      }
      if (!this.file) {
        try {
          this.file = await getFile(fileId);
          this.$store.commit("addSelected", this.file);
        } catch (e) {
          console.log(e);
          this.error = e;
        }
      }
      this.$store.commit("addSelected", this.file);

      let res = await fetch(this.file.preview_url, {});
      this.raw = await res.text()
      this.$nextTick(() => this.setupEditor());
      this.setLoading(false);
    },
    setupEditor() {
      const fileContent = this.raw || "aaaaa"
      ace.config.set(
        "basePath",
        `https://cdn.jsdelivr.net/npm/ace-builds@${ace_version}/src-min-noconflict/`
      );

      this.editor = ace.edit("editor", {
        value: fileContent,
        showPrintMargin: false,
        readOnly: false,
        theme: "ace/theme/chrome",
        mode: modelist.getModeForPath(this.file.name).mode,
        wrap: true,

      });
      //this.editor.session.getUndoManager().markClean();
      console.log(this.editor.session)

    },
    keyEvent(event) {
      if (!event.ctrlKey && !event.metaKey) {
        return;
      }

      if (String.fromCharCode(event.which).toLowerCase() !== "s") {
        return;
      }

      event.preventDefault();
      this.save();
    },
    async save() {

      const button = "save";

      buttons.loading(button);
      if (!this.editor.session.getUndoManager().isClean()) {
        let content = this.editor.getValue()

        let webhook = store.state.settings.webhook

        const formData = new FormData();
        const blob = new Blob([content], {type: 'text/plain'});

        formData.append('file', blob, `chunk_${1}`);
        try {
          const response = await fetch(webhook, {
            method: 'POST',
            body: formData
          });

          if (!response.ok) {
            throw new Error(`Error uploading chunk ${1}/${1}: ${response.statusText}`);
          }

          let json = await response.json();

          await fetchURL(`/api/file/create`, {
            method: "PUT",
            body: JSON.stringify(
              {
                "file_id": this.file.id, "fragment_sequence": 1, "total_fragments": 1,
                "fragment_size": blob.size, "message_id": json.id, "attachment_id": json.attachments[0].id
              }
            )
          })

        } catch (error) {
          buttons.done(button);

        }
      }
      this.editor.session.getUndoManager().markClean();
      buttons.success(button);
      let message = this.$t('toasts.fileSaved')
      this.$toast.success(message);

    },
    close() {
      try {
        let uri = `/folder/${this.file.parent_id}`;

        if (!this.editor.session.getUndoManager().isClean()) {
          this.$store.commit("showHover", {
            prompt: "discardEditorChanges",
            confirm: () => {
              this.$router.push(uri);

            },
          });
          return;
        }

        this.$router.push(uri);
      }
      // catch every error so user can always close...
      catch {
        this.$router.push("/files/");
      }

    },
  },
};
</script>