<template>
  <div>
    <ul class="file-list">
      <li
        v-for="item in dirs"
        @click="itemClick"
        @touchstart="touchstart"
        @dblclick="next"
        role="button"
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
      {{ $t("prompts.currentlyNavigating") }} <code>{{ nav }}</code
      >.
    </p>
  </div>
</template>

<script>
import { mapState } from "vuex";
import {getItems} from "@/api/folder.js";

export default {
  name: "file-list",
  data: function () {
    return {
      touches: {
        id: "",
        count: 0,
      },
      selected: null,

    };
  },
  computed: {

    ...mapState(["items", "currentFolder", "user"]),
    nav() {
      return decodeURIComponent(this.current);
    },
    dirs() {
      return this.fillOptions()
    }
  },
  mounted() {
    this.fillOptions();
  },
  methods: {

    fillOptions() {
      // Sets the current path and resets
      // the current items.

        const dirs = this.items.filter(item => item.isDir);

        this.$emit("update:selected", dirs);
        return dirs



    },
    next: function (event) {
      // Retrieves the URL of the directory the user
      // just clicked in and fill the options with its
      // content.
      let current = event.currentTarget.dataset.item;
      current = JSON.parse(current)

      let res = getItems("/files/folder/" + current.id).then(this.fillOptions).catch(this.$showError);
      const dirs = res.children.filter(item => item.isDir);

      this.$emit("update:selected", dirs);
      return dirs

    },
    touchstart(event) {
      let url = event.currentTarget.dataset.url;

      // In 300 milliseconds, we shall reset the count.
      setTimeout(() => {
        this.touches.count = 0;
      }, 300);

      // If the element the user is touching
      // is different from the last one he touched,
      // reset the count.
      if (this.touches.id !== url) {
        this.touches.id = url;
        this.touches.count = 1;
        return;
      }

      this.touches.count++;

      // If there is more than one touch already,
      // open the next screen.
      if (this.touches.count > 1) {
        this.next(event);
      }
    },
    itemClick: function (event) {
      if (this.user.singleClick) this.next(event);
      else this.select(event);
    },
    select: function (event) {
      // If the element is already selected, unselect it.
      if (this.selected === event.currentTarget.dataset.item) {
        this.selected = null;
        this.$emit("update:selected", this.current);
        return;
      }

      // Otherwise select the element.
      this.selected = event.currentTarget.dataset.item;
      this.$emit("update:selected", this.selected);
    },
    createDir: async function () {
      this.$store.commit("showHover", {
        prompt: "newDir",
        action: null,
        confirm: null,
        props: {
          redirect: false,
          base: this.current === this.$route.path ? null : this.current,
        },
      });
    },
  },
};
</script>
