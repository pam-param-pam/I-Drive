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

    <span v-for="folder in breadcrumbs" :key="folder.id">
      <span class="chevron">
        <i class="material-icons">keyboard_arrow_right</i>
      </span>
      <component
        draggable="false"
        :is="element"
        :to="base + `/` + folder.id"
        @dragover="dragOver"
        @drop="drop"
      >
        {{ folder.name }}
      </component>
    </span>
  </div>
</template>


<script>
import {mapState} from "vuex"

export default {
  name: "breadcrumbs",
  props: ["base", "noLink", "folderList"],

  computed: {
    ...mapState(["currentFolder", "reload"]),
    element() {
      if (this.noLink !== undefined) {
        return "span"
      }

      return "router-link"

    },
    maxBreadcrumbs() {
      return 5
      if (this.isMobile()) {
        return 3
      } else return 5
    },
    breadcrumbs() {
      if (this.folderList.length >= this.maxBreadcrumbs) {
        while (this.folderList.length !== this.maxBreadcrumbs) {
          this.folderList.shift()
        }

        this.folderList[0].name = "..."
      }

      return this.folderList
    },

  },
  methods: {
    isMobile() {
      return window.innerWidth <= 950

    },
    dragOver: function (event) {
      console.log("DRAG OVER EVENT")
      console.log(event)

      // if (!this.canDrop) return
      //
      // event.preventDefault()
      // let el = event.target
      //
      // for (let i = 0; i < 5; i++) {
      //   if (!el.classList.contains("item")) {
      //     el = el.parentElement
      //   }
      // }
      //
      // el.style.opacity = 1

    },
    drop: async function (event) {
      console.log("DROP EVENT")
      console.log(event)
    },
  },


}
</script>