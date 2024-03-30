<template>
  <div class="breadcrumbs">
    <component
      :is="element"
      :to="base || ''"
      :aria-label="$t('files.home')"
      :title="$t('files.home')"
      draggable="false"
    >
      <i class="material-icons">home</i>
    </component>
    <span v-for="folder in path" :key="folder.id">
          <span class="chevron"
          ><i class="material-icons">keyboard_arrow_right</i></span
          >
        <component draggable="false" :is="element" :to="folder.id">{{ folder.name }} </component>

    </span>

  </div>
</template>

<script>
import {mapState} from "vuex";
import {breadcrumbs} from "@/api/folder.js";

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
        let path = [];

        if (this.currentFolder) {
          try {
            path = await breadcrumbs(this.currentFolder.id);
          }
          catch (error) {
            console.log(error)
          }
        }

        return path
      },
      default: [],

    },
  },

};
</script>

<style></style>