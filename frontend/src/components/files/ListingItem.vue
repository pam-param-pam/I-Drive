<template>
  <div
    class="item"
    role="button"
    tabindex="0"
    :draggable="isDraggable"
    @dragstart="dragStart"
    @dragover="dragOver"
    @drop="drop"
    @click="itemClick"
    :data-dir="isDir"
    :data-type="type"
    :aria-label="name"
    :aria-selected="isSelected"
  >
    <div>

      <i class="material-icons"></i>
    </div>

    <div>
      <p class="name">{{ name }}</p>


      <p v-if="isDir" class="size" data-order="-1">&mdash;</p>
      <p v-else class="size" :data-order="size">{{ humanSize() }}</p>


      <p class="created">
      <time :datetime="created">{{ humanTime() }}</time>
      </p>

    </div>
  </div>
</template>

<script>
import { enableThumbs } from "@/utils/constants";
import { mapMutations, mapGetters, mapState } from "vuex";
import { filesize } from "@/utils";
import moment from "moment";
import { files as api } from "@/api";
import * as upload from "@/utils/upload";

export default {

  name: "item",
  data: function () {
    return {
      touches: 0,
    };
  },
  props: [
    "name",
    "id",
    "extension",
    "streamable",
    "ready",
    "owner",
    "encrypted_size",
    "parent_id",
    "isDir",
    "size",
    "index",
    "readOnly",
    "created",
  ],
  computed: {
    ...mapState(["user", "perms", "selected", "items"]),
    ...mapGetters(["selectedCount"]),
    singleClick() {
      return this.readOnly === undefined && this.user.singleClick;
    },
    item() {
       return {
           index: this.index,
           name: this.name,
           id: this.id,
           extension: this.extension,
           streamable:this.streamable,
           ready: this.ready,
           owner: this.owner,
           encrypted_size: this.encrypted_size,
           parent_id: this.parent_id,
           isDir: this.isDir,
           size: this.size,
           readOnly: this.readOnly,
           created: this.created,
       }
    },
    type() {
        if (this.extension === ".mp4") {
            return "video";
        }
        if (this.extension === ".mp3") {
            return "song";
        }
        if (this.extension === ".txt") {
            return "text";
        }
        if (this.extension === ".jpg" || this.extension === ".png") {
            return "image";
        }

        return "unknown";
    },
    isSelected() {

      return this.selected.indexOf(this.item) !== -1;
    },
    isDraggable() {
      return this.readOnly === undefined && this.perms.rename;
    },
    canDrop() {
      if (!this.isDir || this.readOnly !== undefined) return false;


      for (let i of this.selected) {
        if (this.items[i] === this.item) {
          return false;
        }
      }

      return true;
    },

  },
  methods: {
    ...mapMutations(["addSelected", "removeSelected", "resetSelected"]),
    humanSize: function () {
      return this.type === "invalid_link" ? "invalid link" : filesize(this.size);
    },
    humanTime: function () {
      if (this.readOnly === undefined && this.user.dateFormat) {
        return moment(this.created).format("L LT");
      }
      return moment(this.created).fromNow();
    },
    dragStart: function () {
      if (this.selectedCount === 0) {
        this.addSelected(this.item);
        return;
      }

      if (!this.isSelected) {
        this.resetSelected();
        this.addSelected(this.item);
      }
    },
    dragOver: function (event) {
      if (!this.canDrop) return;

      event.preventDefault();
      let el = event.target;

      for (let i = 0; i < 5; i++) {
        if (!el.classList.contains("item")) {
          el = el.parentElement;
        }
      }

      el.style.opacity = 1;
    },
    drop: async function (event) {
        //nie kumam co tu sie dzieje LOL
      if (!this.canDrop) return;
      event.preventDefault();

      if (this.selectedCount === 0) return;

      let el = event.target;
      for (let i = 0; i < 5; i++) {
        if (el !== null && !el.classList.contains("item")) {
          el = el.parentElement;
        }
      }

      let items = [];

      for (let i of this.selected) {
          //xdddddddddddd
          /*
        items.push({
          from: this.req.items[i].url,
          to: this.url + encodeURIComponent(this.req.items[i].name),
          name: this.req.items[i].name,
        });

           */
      }

      // Get url from ListingItem instance
      let path = el.__vue__.url;
      let baseItems = (await api.fetch(path)).items;

      let action = (overwrite, rename) => {
        api
          .move(items, overwrite, rename)
          .then(() => {
            this.$store.commit("setReload", true);
          })
          .catch(this.$showError);
      };

      let conflict = upload.checkConflict(items, baseItems);

      let overwrite = false;
      let rename = false;

      if (conflict) {
        this.$store.commit("showHover", {
          prompt: "replace-rename",
          confirm: (event, option) => {
            overwrite = option === "overwrite";
            rename = option === "rename";

            event.preventDefault();
            this.$store.commit("closeHovers");
            action(overwrite, rename);
          },
        });

        return;
      }

      action(overwrite, rename);
    },
    itemClick: function (event) {
      if (this.singleClick && !this.$store.state.multiple) this.open();
      else this.click(event);
    },
    click: function (event) {
      if (!this.singleClick && this.selectedCount !== 0) event.preventDefault();

      setTimeout(() => {
        this.touches = 0;
      }, 250);

      this.touches++;
      if (this.touches > 1) {
        this.open();
      }

      if (this.$store.state.selected.indexOf(this.item) !== -1) {
        this.removeSelected(this.item);
        return;
      }

      if (event.shiftKey && this.selected.length > 0) {
        let fi = 0;
        let la = 0;

        if (this.index > this.selected[0].index) {
          fi = this.selected[0].index + 1;
          la = this.index;
        } else {
          fi = this.index;
          la = this.selected[0].index - 1;
        }


        for (; fi <= la; fi++) {
            this.$store.state.items.forEach(item => {
                // Perform actions on each item in the array
                // Add your logic here
                if (item.index === fi) this.addSelected(item)
            });
        }

        return;
      }

      if (
        !this.singleClick &&
        !event.ctrlKey &&
        !event.metaKey &&
        !this.$store.state.multiple
      )
        this.resetSelected();
      this.addSelected(this.item);
    },
    open: function () {
      if (this.isDir)  {
          this.$router.push({ path: `/folder/${this.id}` });
          this.$store.commit("setCurrentFolder", this.item);

      }
      else {
          this.$router.push({ path: `/preview/${this.id}` });
      }
    },
  },
};
</script>
