<template>
    <div id="editor-container">
        <header-bar>
            <action icon="close" :label="$t('buttons.close')" @action="close()" />
            <title>{{ file.name }}</title>

            <action
                v-if="perms.modify"
                id="save-button"
                icon="save"
                :label="$t('buttons.save')"
                @action="save()"
            />
        </header-bar>

        <breadcrumbs base="/files/"/>

        <form id="editor"></form>
    </div>
</template>

<script>
import {mapState} from "vuex";
import {files as api} from "@/api";
import {theme} from "@/utils/constants";
import buttons from "@/utils/buttons";
import url from "@/utils/url";

import {version as ace_version} from "ace-builds";
import ace from "ace-builds/src-min/ace.js"
import modelist from "ace-builds/src-min-noconflict/ext-modelist.js"

import HeaderBar from "@/components/header/HeaderBar.vue";
import Action from "@/components/header/Action.vue";
import Breadcrumbs from "@/components/Breadcrumbs.vue";
import {getFile} from "@/api/files.js";
import {getItems} from "@/api/folder.js";

export default {
    name: "editor",
    components: {
        HeaderBar,
        Action,
        Breadcrumbs,
    },
    computed: {
        ...mapState(["perms", "currentFolder"]),

    },
    data: function () {
        return {
            file: null,

        };
    },

    created() {
        console.log("aaaaaaaaaa")
        this.fetchData()

        window.addEventListener("keydown", this.keyEvent);
    },
    beforeDestroy() {
        window.removeEventListener("keydown", this.keyEvent);
        this.editor.destroy();
    },
    mounted: function () {
        /*
        const fileContent = this.file.content || "aaaaaaaaaaa";

        ace.config.set(
            "basePath",
            `https://cdn.jsdelivr.net/npm/ace-builds@${ace_version}/src-min-noconflict/`
        );

        this.editor = ace.edit("editor", {
            value: fileContent,
            showPrintMargin: false,
            readOnly: false,
            theme: "ace/theme/chrome",
            mode: modelist.getModeForPath(this.req.name).mode,
            wrap: true,
        });

        if (theme === "dark") {
            this.editor.setTheme("ace/theme/twilight");
        }

         */
    },
    methods: {
        async fetchData() {

            let fileId = this.$route.params.fileId;

            this.setLoading(true);

            try {
                this.file = await getFile(fileId)
                if (!this.currentFolder) {
                    const res = await getItems(this.file.parent_id);

                    this.$store.commit("setItems", res.children);
                    this.$store.commit("setCurrentFolder", res);

                }
                this.$store.commit("addSelected", this.file);

            } catch (e) {
                console.log(e)
                this.error = e;
            } finally {
                this.setLoading(false);

            }
        },
        back() {
            let uri = url.removeLastDir(this.$route.path) + "/";
            this.$router.push({path: uri});
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
            /*
            const button = "save";
            buttons.loading("save");

            try {
                await api.put(this.$route.path, this.editor.getValue());
                buttons.success(button);
            } catch (e) {
                buttons.done(button);
                this.$showError(e);
            }

             */
        },
        close() {
            this.$store.commit("updateItems", {});
            let uri = `/folder/${this.file.parent_id}`

            this.$router.push({path: uri});
        },
    },
};
</script>
