<template>
  <div>
    <header-bar showMenu="false" showLogo="false">
      <search/>
      <title/>
      <action
        class="search-button"
        icon="search"
        :label="$t('buttons.search')"
        @action="openSearch()"
      />

      <template #actions>
        <template v-if="!isMobile">
          <action
            v-if="headerButtons.share"
            icon="share"
            :label="$t('buttons.share')"
            show="share"
          />
          <action
            v-if="headerButtons.rename"
            icon="mode_edit"
            :label="$t('buttons.rename')"
            show="rename"
          />
          <action
            v-if="headerButtons.lock"
            id="lock-button"
            icon="lock"
            :label="$t('buttons.lockFolder')"
            show="editFolderPassword"
          />
          <action
            v-if="headerButtons.move"
            id="move-button"
            icon="forward"
            :label="$t('buttons.moveFile')"
            show="move"
          />
          <action
            v-if="headerButtons.delete"
            id="delete-button"
            icon="delete"
            :label="$t('buttons.delete')"
            show="delete"
          />

        </template>

        <action
          v-if="headerButtons.shell"
          icon="code"
          :label="$t('buttons.shell')"
          @action="$store.commit('toggleShell')"
        />
        <action
          :icon="viewIcon"
          :label="$t('buttons.switchView')"
          @action="switchView"
        />
        <action
          v-if="headerButtons.download"
          icon="file_download"
          :label="$t('buttons.download')"
          @action="download"
          :counter="selectedCount"
        />
        <action
          v-if="headerButtons.upload"
          icon="file_upload"
          id="upload-button"
          :label="$t('buttons.upload')"
          @action="upload"
        />
        <action icon="info" :label="$t('buttons.info')" show="info"/>


      </template>
    </header-bar>

    <div v-if="isMobile" id="file-selection">
      <span v-if="selectedCount > 0">{{ selectedCount }} selected</span>
      <action
        v-if="headerButtons.share"
        icon="share"
        :label="$t('buttons.share')"
        show="share"
      />
      <action
        v-if="headerButtons.rename"
        icon="mode_edit"
        :label="$t('buttons.rename')"
        show="rename"
      />
      <action
        v-if="headerButtons.lock"
        icon="lock"
        :label="$t('buttons.lockFolder')"
        show="editFolderPassword"
      />
      <action
        v-if="headerButtons.move"
        icon="forward"
        :label="$t('buttons.moveFile')"
        show="move"
      />
      <action
        v-if="headerButtons.delete"
        icon="delete"
        :label="$t('buttons.delete')"
        show="delete"
      />
    </div>

    <div v-if="loading">
      <h2 class="message delayed">
        <div class="spinner">
          <div class="bounce1"></div>
          <div class="bounce2"></div>
          <div class="bounce3"></div>
        </div>
        <span>{{ $t("files.loading") }}</span>
      </h2>
    </div>
    <template v-else-if="error == null">

      <div v-if="dirsSize + filesSize === 0">
        <h2 class="message">
          <a href="https://www.youtube.com/watch?app=desktop&v=nGBYEUNKPmo">
            <img
              src="https://steamuserimages-a.akamaihd.net/ugc/2153341894595795931/DCCF2A0051A51653A133FB1A8123EA4D3696AB6C/?imw=637&imh=358&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=true"
              alt="You look lonely, I can fix that~">
          </a>
        </h2>
        <input
          style="display: none"
          type="file"
          id="upload-input"
          @change="uploadInput($event)"
          multiple
        />
        <input
          style="display: none"
          type="file"
          id="upload-folder-input"
          @change="uploadInput($event)"
          webkitdirectory
          multiple
        />
      </div>
      <div
        v-else
        id="listing"
        ref="listing"
        :class="settings.viewMode + ' file-icons'"
        @dragenter.prevent @dragover.prevent
      >
        <div>
          <div class="item header">
            <div></div>
            <div>
              <p
                :class="{ active: nameSorted }"
                class="name"
                role="button"
                tabindex="0"
                @click="sort('name')"
                :title="$t('files.sortByName')"
                :aria-label="$t('files.sortByName')"
              >
                <span>{{ $t("files.name") }}</span>
                <i class="material-icons">{{ nameIcon }}</i>
              </p>

              <p
                :class="{ active: sizeSorted }"
                class="size"
                role="button"
                tabindex="0"
                @click="sort('size')"
                :title="$t('files.sortBySize')"
                :aria-label="$t('files.sortBySize')"
              >
                <span>{{ $t("files.size") }}</span>
                <i class="material-icons">{{ sizeIcon }}</i>
              </p>

              <p
                :class="{ active: createdSorted }"
                class="created"
                role="button"
                tabindex="0"
                @click="sort('created')"
                :title="$t('files.sortByCreated')"
                :aria-label="$t('files.sortByCreated')"
              >
                <span>{{ $t("files.created") }}</span>
                <i class="material-icons">{{ createdIcon }}</i>
              </p>
            </div>
          </div>
        </div>

        <h2 v-if="dirsSize > 0">{{ $t("files.folders") }}</h2>
        <div v-if="dirsSize > 0">
          <item
            v-for="item in dirs" :key="item.id"
            :item="item"
          >
          </item>
        </div>

        <h2 v-if="filesSize > 0">{{ $t("files.files") }}</h2>
        <div v-if="filesSize > 0">

          <item
            v-for="item in files" :key="item.id"
            :item="item"
          ></item>

        </div>

        <input
          style="display: none"
          type="file"
          id="upload-input"
          @change="uploadInput($event)"
          multiple
        />
        <input
          style="display: none"
          type="file"
          id="upload-folder-input"
          @change="uploadInput($event)"
          webkitdirectory
          multiple
        />

      </div>
    </template>
  </div>
</template>

<script>
import Vue from "vue";
import {mapGetters, mapMutations, mapState} from "vuex";
import {enableExec, name} from "@/utils/constants";
import * as upload from "@/utils/upload";
import css from "@/utils/css";
import throttle from "lodash.throttle";

import HeaderBar from "@/components/header/HeaderBar.vue";
import Action from "@/components/header/Action.vue";
import Search from "@/components/Search.vue";
import Item from "@/components/files/ListingItem.vue";
import {updateSettings} from "@/api/user.js";
import {getItems} from "@/api/folder.js";
import {sortItems} from "@/api/utils.js";

export default {
  name: "listing",

  props: {
    password: String,
    folderId: String,
  },

  components: {
    HeaderBar,
    Action,
    Search,
    Item,
  },
  data: function () {
    return {
      showLimit: 50,
      columnWidth: 280,
      dragCounter: 0,
      width: window.innerWidth,
      itemWeight: 0,

    };
  },
  computed: {

    ...mapState(["items", "reload", "selected", "settings", "perms", "user", "selected", "loading", "error", "currentFolder", "folderPasswords"]),
    ...mapGetters(["selectedCount", "currentPrompt", "currentPromptName"]),
    nameSorted() {
      return this.settings.sortingBy === "name";
    },
    sizeSorted() {
      return this.settings.sortingBy === "size";
    },
    dirs() {
      const items = [];
      if (this.items != null) {
        this.items.forEach((item) => {
          console.log("name: " + item.name)

          console.log("hideLockedFolders: " + this.settings.hideLockedFolders)
          console.log("locked: " + item.locked)

          if (item.isDir && (!item.locked || !this.settings.hideLockedFolders)) {
            items.push(item);
          }

        });
      }
      return sortItems(items);
    },
    files() {
      const items = [];

      if (this.items != null) {
        this.items.forEach((item) => {
          if (!item.isDir) {
            items.push(item);
          }
        });
      }
      return sortItems(items);
    },
    dirsSize() {
      return this.dirs.length
    },
    filesSize() {
      return this.files.length
    },
    createdSorted() {
      return this.settings.sortingBy === "created";
    },
    ascOrdered() {
      return this.settings.sortByAsc;
    },

    nameIcon() {
      if (this.nameSorted && !this.ascOrdered) {
        return "arrow_upward";
      }

      return "arrow_downward";
    },
    sizeIcon() {
      if (this.sizeSorted && this.ascOrdered) {
        return "arrow_downward";
      }

      return "arrow_upward";
    },
    createdIcon() {
      if (this.createdSorted && this.ascOrdered) {
        return "arrow_downward";
      }

      return "arrow_upward";
    },
    viewIcon() {
      const icons = {
        list: "view_module",
        mosaic: "grid_view",
        "mosaic gallery": "view_list",
      };
      return icons[this.settings.viewMode];
    },
    headerButtons() {
      return {
        upload: this.perms.create,
        download: this.perms.download,
        shell: this.perms.execute && enableExec,
        delete: this.selectedCount > 0 && this.perms.delete,
        rename: this.selectedCount === 1 && this.perms.rename,
        share: this.selectedCount === 1 && this.perms.share,
        move: this.selectedCount > 0 && this.perms.rename,
        copy: this.selectedCount > 0 && this.perms.create,
        lock: this.selectedCount === 1 && this.selected[0].isDir === true && this.perms.delete,
      };
    },
    isMobile() {
      return this.width <= 736;
    },
  },
  watch: {
    $route: "fetchFolder",
    reload: function (value) {
      console.log("reload changed")
      if (value === true) {
        this.fetchFolder();
      }
    },
    items: function () {
      // Ensures that the listing is displayed
      Vue.nextTick(() => {
        // How much every listing item affects the window height
        this.setItemWeight();
        // Fill and fit the window with listing items
        this.fillWindow(true);
      });
    }
  },
  created() {
    this.fetchFolder()

  },

  mounted: function () {
    // Check the columns size for the first time.
    this.columnsResize();

    // How much every listing item affects the window height
    this.setItemWeight();

    // Fill and fit the window with listing items
    this.fillWindow(true);

    // Add the needed event listeners to the window and document.
    window.addEventListener("keydown", this.keyEvent);
    window.addEventListener("scroll", this.scrollEvent);
    window.addEventListener("resize", this.windowsResize);

    if (!this.perms.create) return;
    document.addEventListener("dragover", this.preventDefault);
    document.addEventListener("dragenter", this.dragEnter);
    document.addEventListener("dragleave", this.dragLeave);
    document.addEventListener("drop", this.drop);
  },
  beforeDestroy() {
    // Remove event listeners before destroying this page.
    window.removeEventListener("keydown", this.keyEvent);
    window.removeEventListener("scroll", this.scrollEvent);
    window.removeEventListener("resize", this.windowsResize);

    if (this.user && !this.perms.create) return;
    document.removeEventListener("dragover", this.preventDefault);
    document.removeEventListener("dragenter", this.dragEnter);
    document.removeEventListener("dragleave", this.dragLeave);
    document.removeEventListener("drop", this.drop);
  },
  methods: {

    ...mapMutations(["updateUser", "addSelected", "setLoading", "setError"]),

    async fetchFolder() {

      console.log("loading1: " + this.loading)
      this.setError(null)

      this.setLoading(true);
      console.log("loading2: " + this.loading)

      try {
        const res = await getItems(this.folderId, false);

        this.$store.commit("setItems", res.children);
        this.$store.commit("setCurrentFolder", res);

        if (res.parent_id) { //only set title if its not root folder
          document.title = `${res.name} - ` + name;
        }
        else {
          document.title = name;
        }

      } catch (error) {
        this.setError(error);

        if (error.status === 469) {
          this.$store.commit("showHover", {
            prompt: "FolderPassword",
            props: {folder_id: this.folderId},
            confirm: () => {
              this.fetchFolder();

            },
          });
        }
        console.log(error)
      } finally {
        console.log("loading3: " + this.loading)
        this.setLoading(false);
        console.log("loading4: " + this.loading)

      }
    },


    keyEvent(event) {
      // No prompts are shown
      if (this.currentPrompt !== null) {

        return;
      }

      // Esc!
      if (event.keyCode === 27) {
        // Reset files selection.
        this.$store.commit("resetSelected");
      }

      // Del!
      if (event.keyCode === 46) {
        if (!this.perms.delete || this.selectedCount === 0) return;

        // Show delete prompt.
        this.$store.commit("showHover", "delete");
      }

      // F1!
      if (event.keyCode === 112) {
        event.preventDefault()
        // Show delete prompt.
        this.$store.commit("showHover", "info");
      }

      // F2!
      if (event.keyCode === 113) {
        if (!this.perms.rename || this.selectedCount !== 1) return;

        // Show rename prompt.
        this.$store.commit("showHover", "rename");
      }

      // Ctrl is pressed
      if (event.ctrlKey || event.metaKey) {

        let key = String.fromCharCode(event.which).toLowerCase();

        switch (key) {
          case "f":
            event.preventDefault();
            this.$store.commit("showHover", "search");
            break;
          case "a":
            event.preventDefault();
            for (let file of this.files) {
              if (this.$store.state.selected.indexOf(file.index) === -1) {
                this.addSelected(file.index);
              }
            }
            for (let dir of this.dirs) {
              if (this.$store.state.selected.indexOf(dir.index) === -1) {
                this.addSelected(dir.index);
              }
            }
            break;

        }
      }

    },


    columnsResize() {
      // Update the columns size based on the window width.
      let items = css(["#listing.mosaic .item", ".mosaic#listing .item"]);
      if (!items) return;

      let columns = Math.floor(
        document.querySelector("main").offsetWidth / this.columnWidth
      );
      if (columns === 0) columns = 1;
      items.style.width = `calc(${100 / columns}% - 1em)`;
    },
    scrollEvent: throttle(function () {
      const totalItems = this.filesSize + this.dirsSize;

      // All items are displayed
      if (this.showLimit >= totalItems) return;

      const currentPos = window.innerHeight + window.scrollY;

      // Trigger at the 75% of the window height
      const triggerPos = document.body.offsetHeight - window.innerHeight * 0.25;

      if (currentPos > triggerPos) {
        // Quantity of items needed to fill 2x of the window height
        const showQuantity = Math.ceil(
          (window.innerHeight * 2) / this.itemWeight
        );

        // Increase the number of displayed items
        this.showLimit += showQuantity;
      }
    }, 100),
    dragEnter() {
      this.dragCounter++;

      // When the user starts dragging an item, put every
      // file on the listing with 50% opacity.
      let items = document.getElementsByClassName("item");

      Array.from(items).forEach((file) => {
        file.style.opacity = 0.5;
      });
    },
    dragLeave() {
      this.dragCounter--;

      if (this.dragCounter === 0) {
        this.resetOpacity();
      }
    },
    preventDefault(event) {
      // Wrapper around prevent default.
      event.preventDefault();
    },

    drop: async function (event) {
      event.preventDefault();
      this.dragCounter = 0;
      this.resetOpacity();
      let dt = event.dataTransfer;
      console.log(dt.files)
      let el = event.target;

      if (dt.files.length <= 0) return;

      for (let i = 0; i < 5; i++) {
        if (el !== null && !el.classList.contains("item")) {
          el = el.parentElement;
        }
      }
      console.log(el)
      this.dropHandler(event)
      console.log(dt)
      let files = await upload.scanFiles(dt);
      console.log(files)
      let parent_id = this.currentFolder.id
      if (el !== null && el.classList.contains("item") && el.dataset.dir === "true") {
        parent_id = el.__vue__.item.id;

      }
      console.log(parent_id)

      //upload.handleFiles(files, path);
    },

    async uploadInput(event) {
      this.$store.commit("closeHover");

      let files = event.currentTarget.files;
      let folder = this.currentFolder

      this.$toast.info(this.$t("toasts.PreparingUpload"))
      await upload.prepareForUpload(files, folder)


    },
    resetOpacity() {
      let items = document.getElementsByClassName("item");

      Array.from(items).forEach((file) => {
        file.style.opacity = 1;
      });
    },
    async sort(by) {
      let asc = false;

      if (by === "name") {
        if (this.nameIcon === "arrow_upward") {
          asc = true;
        }
      } else if (by === "size") {
        if (this.sizeIcon === "arrow_upward") {
          asc = true;
        }
      } else if (by === "created") {
        if (this.createdIcon === "arrow_upward") {
          asc = true;
        }
      }
      try {
        await updateSettings({"sortingBy": by, "sortByAsc": asc})

      } catch (e) {
        console.log(e)
        this.$toast.error(e)
      }

      this.$store.commit("setSortingBy", by);
      this.$store.commit("setSortByAsc", asc);
      let items = sortItems(this.items)
      this.$store.commit("setItems", items);


    },
    openSearch() {
      this.$store.commit("showHover", "search");
    },

    windowsResize: throttle(function () {
      this.columnsResize();
      this.width = window.innerWidth;

      // Listing element is not displayed
      if (this.$refs.listing == null) return;

      // How much every listing item affects the window height
      this.setItemWeight();

      // Fill but not fit the window
      this.fillWindow();
    }, 100),
    download() {
      if (this.selectedCount === 0) {
        let message = this.$t('toasts.selectFilesFirst')

        this.$toast.info(message)
      } else {
        let filesNum = 0
        this.selected.forEach(item => {

          if (!item.isDir) {
            window.open(item.download_url, '_blank');
            filesNum++
          }
        })
        if (filesNum > 0) {
          this.$toast.success(`Downloading ${filesNum} files`)
          this.$store.commit("resetSelected");
        } else {
          this.$toast.info(`You can't download a folder >-<`)

        }


      }
    },
    switchView: async function () {
      this.$store.commit("closeHover");

      const modes = {
        list: "mosaic",
        mosaic: "mosaic gallery",
        "mosaic gallery": "list",
      };

      const data = {
        viewMode: modes[this.settings.viewMode] || "list",
      };

      // Await ensures correct value for setItemWeight()
      await this.$store.commit("updateSettings", data);


      this.setItemWeight();
      this.fillWindow();

      try {
        await updateSettings(data)
      } catch (error) {
        console.log(error)
      }


    },
    upload: function () {
      if (
        typeof window.DataTransferItem !== "undefined" &&
        typeof DataTransferItem.prototype.webkitGetAsEntry !== "undefined"
      ) {
        this.$store.commit("showHover", "upload");
      } else {
        document.getElementById("upload-input").click();
      }
    },
    setItemWeight() {

      if (this.$refs.listing == null || this.currentFolder == null) return;


      let itemQuantity = this.filesSize + this.dirsSize;
      if (itemQuantity > this.showLimit) itemQuantity = this.showLimit;

      // How much every listing item affects the window height
      this.itemWeight = this.$refs.listing.offsetHeight / itemQuantity;
    },
    fillWindow(fit = false) {
      if (this.currentFolder == null) return;

      const totalItems = this.filesSize + this.dirsSize;

      // More items are displayed than the total
      if (this.showLimit >= totalItems && !fit) return;

      const windowHeight = window.innerHeight;

      // Quantity of items needed to fill 2x of the window height
      const showQuantity = Math.ceil(
        (windowHeight + windowHeight * 2) / this.itemWeight
      );

      // Less items to display than current
      if (this.showLimit > showQuantity && !fit) return;

      // Set the number of displayed items
      this.showLimit = showQuantity > totalItems ? totalItems : showQuantity;
    },
  },
};
</script>
