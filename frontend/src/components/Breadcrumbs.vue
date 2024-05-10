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
        <component draggable="false" :is="element" :to="`/folder/` + folder.id">{{ folder.name }} </component>

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
    maxBreadcrumbs() {
      return 5
      if (this.isMobile()) {
        return 3
      }
      else return 5
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

            if (path.length >= this.maxBreadcrumbs) {
              while (path.length !== this.maxBreadcrumbs) {
                path.shift();
              }

              path[0].name = "...";
            }


          }
          catch (error) {
            console.log(error)
          }
        }




        return path;
      },
      default: [],

    },
  },

};
</script>