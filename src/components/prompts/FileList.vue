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
      {{ $t("prompts.moveTo") }} <code>{{ nav?.name }}</code
      >.
    </p>
  </div>
</template>

<script>
import { mapState } from "vuex"
import {getDirs} from "@/api/folder.js"

export default {
  name: "file-list",
  data() {
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
  },
  methods: {
    async fetchData(folder) {
      let res = await getDirs(folder.id)
      let dirs = res.children

      if (res.parent_id) {
        let folderBack = {name: "...", id: res.parent_id}
        dirs.unshift(folderBack)
      }

      this.dirs = dirs
      this.nav = {name: res.name, id: res.id}
      this.$emit("update:current", this.nav)
    },

    async next(event) {
      let current = event.currentTarget.dataset.item
      current = JSON.parse(current)
      await this.fetchData(current)

    },

    select: function (event) {

    },
    createDir: async function () {
      this.$store.commit("showHover", {
        prompt: "newDir",

      })
    },
  },
}
</script>
