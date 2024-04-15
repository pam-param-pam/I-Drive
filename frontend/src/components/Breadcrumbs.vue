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
  methods: {
    isMobile() {
      return window.innerWidth <= 736;

    }
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
        const maxWidth = window.innerWidth; // Assuming window width as the maximum width in pixels

        let currentWidth = 0;
        let trimmedPath = [];

        for (let folder of path) {
          const folderWidth = (folder.name.length + 3)* 16 ; // Assuming average character width of 8px and adding 3 for characters like space and '...'

          if (currentWidth + folderWidth <= maxWidth) {
            trimmedPath.push(folder);
            currentWidth += folderWidth;
          } else {
            // If adding this folder exceeds the width, stop and add "..."
            let changed_folder = folder
            changed_folder.name = "..."
            trimmedPath.push(changed_folder);
            break;
          }
        }

        return trimmedPath;
      },
      default: [],

    },
  },

};
</script>

<style>

</style>