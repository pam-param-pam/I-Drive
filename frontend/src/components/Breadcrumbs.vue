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

    <span v-for="(folder, index) in path" :key="index">
      <span class="chevron"
        ><i class="material-icons">keyboard_arrow_right</i></span
      >
      <component :is="element" :to="folder.id">{{ folder.name }}</component>
    </span>
  </div>
</template>

<script>
import {files as api} from "@/api/index.js";
import prettyBytes from "pretty-bytes";

export default {
  name: "breadcrumbs",
  props: ["base", "noLink"],
    data() {
        return {
            path: []
        }
    },
  watch: {
    $route: "fetchPath",
    reload: function (value) {
      if (value === true) {
        this.fetchPath();
      }
    },
  },
  methods: {
    async fetchPath() {
      let path = [];

      let folder_id = this.$router.currentRoute.path.replace("/files/folder/", "")
      try {
          path = await api.breadcrumbs(folder_id);

      } catch (error) {
          this.$showError(error);
      }
      this.path = path
    },
  },
  computed: {


    element() {
      if (this.noLink !== undefined) {
        return "span";
      }

      return "router-link";
    },
  },
};
</script>

<style></style>
