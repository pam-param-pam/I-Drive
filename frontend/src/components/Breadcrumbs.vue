<template>
    <div class="breadcrumbs">
        <component
                :is="element"
                :to="base || ''"
                :aria-label="$t('files.home')"
                :title="$t('files.home')"
        >
            <i class="material-icons">home</i>
        </component>
        <span v-for="(folder, index) in path" :key="folder.id">
          <span class="chevron"
          ><i class="material-icons">keyboard_arrow_right</i></span
          >
        <component :is="element" :to="folder.id">{{ folder.name }}</component>
    </span>

    </div>
</template>

<script>
import {files as api} from "@/api/index.js";
import {mapState} from "vuex";

export default {
    name: "breadcrumbs",
    props: ["base", "noLink"],

    computed: {
        ...mapState(["currentFolder", "reload"]),
        element() {
            if (this.noLink !== undefined) {
                return "span";
            }

            return "router-link";
        },
    },

    asyncComputed: {
        path: {
            async get() {

                console.log("fetchPath!!!")
                let path = [];


                try {
                    let folder_id = ""
                    if (!this.currentFolder) {
                        folder_id= "/files/"
                    }
                    else {
                        folder_id = this.currentFolder.id

                    }

                    path = await api.breadcrumbs(folder_id);
                    console.log("path" + JSON.stringify(path))
                } catch (error) {
                    this.$showError(error);
                }
                return path
            },
            default: [],

        },
    },




};
</script>

<style></style>