<template>
  <div>
    <header-bar showMenu="false" showLogo="false">
      <template>
        <Search
          @onSearchQuery="onSearchQuery"
          @exit="onSearchClosed"
        />
      </template>
      <title></title>
      <template #actions>
        <template v-if="!isMobile">
          <action
            v-if="headerButtons.locate"
            icon="location_on"
            :label="$t('buttons.locate')"
            @action="locateItem"
          />
          <action
            v-if="headerButtons.share"
            icon="share"
            :label="$t('buttons.share')"
            show="share"
          />
          <action
            v-if="headerButtons.modify"
            icon="mode_edit"
            :label="$t('buttons.rename')"
            show="rename"
          />

          <action
            v-if="headerButtons.modify"
            id="move-button"
            icon="forward"
            :label="$t('buttons.moveFile')"
            show="move"
          />
          <action
            v-if="headerButtons.moveToTrash"
            id="moveToTrash-button"
            icon="delete"
            :label="$t('buttons.moveToTrash')"
            show="moveToTrash"
          />
          <action
            v-if="headerButtons.restore"
            icon="restore"
            :label="$t('buttons.restoreFromTrash')"
            show="restoreFromTrash"
          />

        </template>
        <action
          v-if="headerButtons.lock"
          icon="lock"
          :label="$t('buttons.lockFolder')"
          show="editFolderPassword"
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
          :disabled="isSearchActive && !selectedCount > 0 "
          icon="file_upload"
          id="upload-button"
          :label="$t('buttons.upload')"
          @action="upload"
        />
        <action
          v-if="headerButtons.shell"
          icon="code"
          :label="$t('buttons.shell')"
          @action="$store.commit('toggleShell')"
        />
        <action
          :icon="viewIcon"
          :label="$t('buttons.switchView')"
          @action="onSwitchView"
        />
        <action
          v-if="headerButtons.info"
          icon="info"
          :disabled="isSearchActive && !selectedCount > 0"
          :label="$t('buttons.info')"
          show="info"
        />
      </template>

    </header-bar>

    <div v-if="isMobile" id="file-selection">
      <span v-if="selectedCount > 0">{{ selectedCount }} selected</span>
      <action
        v-if="headerButtons.locate"
        icon="location_on"
        :label="$t('buttons.locate')"
        @action="locateItem"
      />
      <action
        v-if="headerButtons.restore"
        icon="restore"
        :label="$t('buttons.restoreFromTrash')"
        show="restoreFromTrash"
      />
      <action
        v-if="headerButtons.share "
        icon="share"
        :label="$t('buttons.share')"
        show="share"
      />
      <action
        v-if="headerButtons.modify"
        icon="mode_edit"
        :label="$t('buttons.rename')"
        show="rename"
      />

      <action
        v-if="headerButtons.modify"
        icon="forward"
        :label="$t('buttons.moveFile')"
        show="move"
      />
      <action
        v-if="headerButtons.moveToTrash"
        icon="delete"
        :label="$t('buttons.moveToTrash')"
        show="moveToTrash"
      />
      <action
        v-if="headerButtons.delete"
        id="delete-button"
        icon="delete"
        :label="$t('buttons.delete')"
        show="delete"
      />
    </div>
    <breadcrumbs v-if="!isSearchActive"
                 base="/files"
                 :folderList="folderList"
    />
    <errors v-if="error" :errorCode="error.response.status"/>


    <h4 v-if="!error && isSearchActive && !loading">{{$t('files.searchItemsFound', {amount: this.items.length})}}</h4>
    <Listing
      ref="listing"
      :locatedItem=locatedItem
      :isSearchActive="isSearchActive"
      @onOpen="onOpen"

    ></Listing>
  </div>
</template>

<script>
import {mapGetters, mapMutations, mapState} from "vuex"

import Breadcrumbs from "@/components/Breadcrumbs.vue"
import Errors from "@/views/Errors.vue"
import Listing from "@/views/files/Listing.vue"
import {getItems} from "@/api/folder.js"
import {name} from "@/utils/constants.js"
import {search} from "@/api/search.js"
import HeaderBar from "@/components/header/HeaderBar.vue"
import axios from "axios"
import Action from "@/components/header/Action.vue";
import Search from "@/components/Search.vue";
import {checkFilesSizes} from "@/utils/upload.js";
import {createZIP} from "@/api/item.js";

export default {
  name: "files",
  components: {
    Search, Action,
    HeaderBar,
    Breadcrumbs,
    Errors,
    Listing,
  },
  props: {
    folderId: String,
    lockFrom: String,
    locatedItem: {},

  },
  data() {
    return {
      items: [],
      isSearchActive: false,
      folderList: [],
      source: null,

    }
  },
  computed: {
    ...mapState(["error", "user", "loading", "selected", "settings", "perms", "selected", "currentFolder", "disabledCreation"]),
    ...mapGetters(["getFolderPassword", "selectedCount"]),

    headerButtons() {
      return {
        info: !this.disabledCreation,
        shell: this.perms.execute,
        upload: this.perms.create,
        download: this.perms.download && this.selectedCount > 0,
        moveToTrash: this.selectedCount > 0 && this.perms.delete,
        modify: this.selectedCount === 1 && this.perms.modify,
        share: this.selectedCount === 1 && this.perms.share,
        lock: this.selectedCount === 1 && this.selected[0].isDir === true && this.perms.lock,
        locate: this.selectedCount === 1 && this.isSearchActive,
      }
    },
    viewIcon() {
      const icons = {
        list: "view_module",
        mosaic: "grid_view",
        "mosaic gallery": "view_list",
      }
      return icons[this.settings.viewMode]
    },
    isMobile() {
      return window.innerWidth <= 736
    },
  },
  created() {
    this.setDisabledCreation(false)

    this.fetchFolder()

  },
  watch: {
    $route: "fetchFolder",
  },
  destroyed() {
    this.$store.commit("setItems", null)
    this.$store.commit("setCurrentFolder", null)

  },
  methods: {
    ...mapMutations(["updateUser", "addSelected", "setLoading", "setError", "setDisabledCreation"]),

    async onSearchClosed() {
      if (this.source) {
        this.source.cancel('Cancelled previous request')
      }

      await this.fetchFolder()
      //todo this breaks shit up with locateItem. possibly race condition, this call  finishes after locateItem

    },
    async download() {
      console.log(this.selectedCount)
      if (this.selectedCount === 1 && !this.selected[0].isDir) {
        window.open(this.selected[0].download_url, '_blank')
        let message = this.$t("toasts.downloadingSingle", {name: this.selected[0].name})
        this.$toast.success(message)

      }
      else {
        const ids = this.selected.map(obj => obj.id);
        let res = await createZIP({"ids": ids})
        window.open(res.download_url, '_blank')

        let message = this.$t("toasts.downloadingZIP")
        this.$toast.success(message)


      }
    },
    async uploadInput(event) {
      this.$store.commit("closeHover")

      let files = event.currentTarget.files
      let folder = this.currentFolder

      if (await checkFilesSizes(files)) {
        this.$store.commit("showHover",  {
          prompt: "NotOptimizedForSmallFiles",
          confirm: () => {
            this.$store.dispatch("upload/upload", {filesList: files, parent_folder: folder})

          },
        })
      }
      else {
        this.$store.dispatch("upload/upload", {filesList: files, parent_folder: folder})
        // await upload.createNeededFolders(files, folder)
      }




    },
    locateItem() {
      this.$emit('onSearchClosed')
      let item = this.selected[0]
      let parent_id = item.parent_id
      console.log("PARENT ID")
      console.log(parent_id)
      this.$router.push({name: "Files", params: {"folderId": "stupidAhHack"}})
      console.log(item)
      this.$router.push({name: "Files", params: {"folderId": parent_id, "locatedItem": item}})

      let message = this.$t("toasts.itemLocated")
      this.$toast.info(message)


    },
    async onSearchQuery(query) {
      this.setLoading(true)


      if (this.source) {
        this.source.cancel('Cancelled previous request')
      }
      this.source = axios.CancelToken.source()
      let realLockFrom = this.lockFrom || this.folderId
      let password = this.getFolderPassword(realLockFrom)
      console.log(password)

      this.items = await search(query, this.source, realLockFrom, password)
      this.setLoading(false)
      this.isSearchActive = true
      this.$store.commit("setItems", this.items)
      this.$store.commit("setCurrentFolder", null)

    },
    upload: function () {
      if (
        typeof window.DataTransferItem !== "undefined" &&
        typeof DataTransferItem.prototype.webkitGetAsEntry !== "undefined"
      ) {
        this.$store.commit("showHover", "upload")
      } else {
        document.getElementById("upload-input").click()
      }
    },

    async fetchFolder() {
      this.isSearchActive = false

      this.searchItemsFound = null

      this.setLoading(true)
      this.setError(null)


      let res = await getItems(this.folderId, this.lockFrom)

      this.items = res.folder.children
      this.folderList = res.breadcrumbs
      this.$store.commit("setItems", this.items)
      this.$store.commit("setCurrentFolder", res.folder)

      if (res.parent_id) { //only set title if its not root folder
        document.title = `${res.name} - ` + name
      }
      else {
        document.title = name
      }

    },
    onSwitchView() {
      this.$refs.listing.switchView();
    },
    onOpen(item) {
      if (item.isDir) {
        if (item.isLocked === true) {
          let password = this.getFolderPassword(item.lockFrom)
          if (!password) {
            this.$store.commit("showHover", {
              prompt: "FolderPassword",
              props: {folderId: item.id, lockFrom: item.lockFrom},
              confirm: () => {
                this.$router.push({name: "Files", params: {"folderId": item.id, "lockFrom": item.lockFrom}})
              },
            })
            return
          }
        }
        this.$router.push({name: "Files", params: {"folderId": item.id, "lockFrom": item.lockFrom}})

      } else {

        if (item.type === "audio" || item.type === "video" || item.type === "image" ||  item.size >= 25 * 1024 * 1024 || item.extension === ".pdf") {
          this.$router.push({name: "Preview", params: {"fileId": item.id, "lockFrom": item.lockFrom}} )

        }
        else {
          this.$router.push({name: "Editor", params: {"fileId": item.id}} )

        }

      }
    }
  },
}
</script>
