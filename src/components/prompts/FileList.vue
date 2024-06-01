<template>
  <div>
    <ul class="file-list">
      <li
        v-for="item in dirs"
        @click="next"
        tabindex="0"
        :aria-label="item.name"
        :aria-selected="selected === item"
        :key="item.id"
        :data-item="JSON.stringify(item)"
      >
        {{ item.name }}
      </li>
    </ul>

    <p>
      {{ $t("prompts.currentlyNavigating") }} <code>{{ nav.name }}</code
      >.
    </p>
  </div>
</template>

<script>
import { mapState } from "vuex"
import {getItems} from "@/api/folder.js"

export default {
  name: "file-list",
  data: function () {
    return {
      selected: null,
      dirs : [],
      nav: null

    }
  },
  computed: {

    ...mapState(["items", "currentFolder", "user"]),


  },

  mounted() {
    this.fetchData(this.currentFolder)
    this.nav = this.currentFolder
  },
  methods: {
    async fetchData(folder) {
      const res = await getItems(folder.id)
      const dirs = res.children.filter(item => item.isDir)

      let folderBack = {name: "...", id: folder.parent_id}



      dirs.unshift(folderBack)
      console.log(dirs)
      this.dirs = dirs
      this.$emit("update:selected", dirs)
      return dirs
    },

    async next(event) {
      // Retrieves the URL of the directory the user
      // just clicked in and fill the options with its
      // content.
      let current = event.currentTarget.dataset.item
      current = JSON.parse(current)
      let dirs = await this.fetchData(current)

      console.log(dirs)
      this.nav = current

    },

    select: function (event) {
      // If the element is already selected, unselect it.
      if (this.selected === event.currentTarget.dataset.item) {
        this.selected = null
        this.$emit("update:selected", this.current)
        return
      }

      // Otherwise select the element.
      this.selected = event.currentTarget.dataset.item
      this.$emit("update:selected", this.selected)
    },
    createDir: async function () {
      this.$store.commit("showHover", {
        prompt: "newDir",
        props: {
          redirect: false,
          base: this.current === this.$route.path ? null : this.current,
        },
      })
    },
  },
}
</script>
