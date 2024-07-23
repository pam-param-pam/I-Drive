<template>
  <div class="card floating">
      <div class="card-title">
          <h2 >{{ $t("prompts.itemInfo") }}</h2>
      </div>

    <div class="card-content">
      <p v-if="selected.length > 1">
        {{ $t("prompts.itemsSelected", { count: selected.length }) }}
      </p>

      <p class="break-word" v-if="name">
        <strong>{{ $t("prompts.displayName") }}:</strong> {{ name }}
      </p>

      <p class="break-word" v-if="id">
          <strong>{{ $t("prompts.identifier") }}:</strong> {{ id }}
      </p>
      <p v-if="inTrashSince">
        <strong>{{ $t("prompts.inTrashSince") }}:</strong> {{ humanTime(inTrashSince) }}
      </p>
      <p v-if="type">
        <strong>{{ $t("prompts.type") }}:</strong> {{ type }}
      </p>

      <p v-if="extension">
          <strong>{{ $t("prompts.extension") }}:</strong> {{ extension }}
      </p>

      <p v-if="size">
          <strong>{{ $t("prompts.size") }}: </strong>
          <code>
              <a @click="changeView($event, 'size')">{{ humanSize(size) }}</a>
          </code>

      </p>

      <p v-if="encryptedSize">
          <strong>{{ $t("prompts.encryptedSize") }}: </strong>
          <code>
              <a @click="changeView($event, 'encryptedSize')">{{ humanSize(encryptedSize) }}</a>
          </code>

      </p>


      <p v-if="streamable">
          <strong>{{ $t("prompts.streamable") }}:</strong>
          <span v-if="streamable" class="checkmark-true"></span> <!-- Green checkmark emoji -->
          <span v-else class="checkmark-false"></span> <!-- Red cross emoji -->
      </p>

      <!--<p v-if="!isDir">-->
      <p v-if="ready">
        <strong>{{ $t("prompts.ready") }}:</strong>
        <span v-if="ready" class="checkmark-true"></span> <!-- Green checkmark emoji -->
        <span v-else class="checkmark-false"></span> <!-- Red cross emoji -->
      </p>

      <p v-if="owner">
          <strong>{{ $t("prompts.owner") }}:</strong> {{ owner }}
      </p>

      <div v-if="resolution">
        <strong>{{ $t("prompts.resolution") }}:</strong>
        {{ resolution.width }} x {{ resolution.height }}
      </div>

      <p v-if="created">
        <strong>{{ $t("prompts.created") }}:</strong> {{ humanTime(created) }}
      </p>
      <p v-if="last_modified">
        <strong>{{ $t("prompts.lastModified") }}:</strong> {{ humanTime(last_modified) }}
      </p>
      <p v-if="iso">
        <strong>{{ $t("prompts.iso") }}:</strong> {{ iso }}
      </p>
      <p v-if="aperture">
        <strong>{{ $t("prompts.aperture") }}:</strong> f/{{ aperture }}
      </p>
      <p v-if="exposureTime">
        <strong>{{ $t("prompts.exposureTime") }}:</strong> {{ exposureTime }} sec
      </p>
      <p v-if="focalLength">
        <strong>{{ $t("prompts.focalLength") }}:</strong> {{ focalLength }}mm
      </p>
      <p v-if="modelName">
        <strong>{{ $t("prompts.modelName") }}:</strong> {{ modelName }}
      </p>
      <template v-if="folderItemsCount">
        <p>
          <strong>{{ $t("prompts.numberFiles") }}:</strong> {{ folderItemsCount.numFiles }}
        </p>
        <p>
          <strong>{{ $t("prompts.numberDirs") }}:</strong> {{ folderItemsCount.numFolders }}
        </p>
      </template>
    </div>

    <div class="card-action">
      <button
        type="submit"
        @click="$store.commit('closeHover')"
        class="button button--flat"
        :aria-label="$t('buttons.ok')"
        :title="$t('buttons.ok')"
      >
        {{ $t("buttons.ok") }}
      </button>
    </div>
  </div>
</template>

<script>
import { mapState, mapGetters } from "vuex"
import { filesize } from "@/utils"
import moment from "moment/min/moment-with-locales.js";


export default {
  name: "info",
  computed: {
    ...mapState(["selected","settings", "currentFolder"]),
    ...mapGetters(["selectedCount"]),
    size() {
      if (this.selectedCount === 0) {
          //return this.currentFolder.size
          return null
          //todo
      }
      if (this.selectedCount >= 1) {
          let sum = 0
          for (let selected of this.selected) {
          if (!selected.isDir) sum += selected.size
        }
        return sum
      }
      return null
    },
    encryptedSize() {
      if (this.selectedCount === 0) {
          //return this.currentFolder.size
          return 0
          //todo
      }

      if (this.selectedCount >= 1) {
          let sum = 0
          for (let selected of this.selected) {
              if (!selected.isDir) sum += selected.encrypted_size
          }
          return sum
      }
      return null
    },
    name() {
      if (this.selectedCount === 0) {
          return this.currentFolder.name

      }
      else if (this.selectedCount === 1) {
          return this.selected[0].name
      }
      return null
    },

    resolution() {
        return null
    },
    created() {
      if (this.selectedCount === 0) {
          return this.currentFolder.created

      }
      else if (this.selectedCount === 1) {
          return this.selected[0].created
      }
      return null

    },
    last_modified() {
      if (this.selectedCount === 0) {
        return this.currentFolder.last_modified

      }
      else if (this.selectedCount === 1) {
        return this.selected[0].last_modified
      }
      return null

    },
    id() {
      if (this.selectedCount === 0) {
          return this.currentFolder.id

      }
      else if (this.selectedCount === 1) {
          return this.selected[0].id
      }
      return null
    },
    ready() {
      if (this.selectedCount === 1) {
          return this.selected[0].ready
      }
      return null

    },
    streamable() {
      if (this.selectedCount === 1) {
        return this.selected[0].streamable
      }
      return null

    },
    type() {
      if (this.selectedCount === 1) {
        return this.selected[0].type
      }
      return null
    },
    iso() {
      if (this.selectedCount === 1) {
        return this.selected[0].iso
      }
      return null
    },
    exposureTime() {
      if (this.selectedCount === 1) {
        return this.selected[0].exposure_time
      }
      return null
    },
    aperture() {
      if (this.selectedCount === 1) {
        return this.selected[0].aperture
      }
      return null
    },
    focalLength() {
      if (this.selectedCount === 1) {
        return this.selected[0].focal_length
      }
      return null
    },
    modelName() {
      if (this.selectedCount === 1) {
        return this.selected[0].model_name
      }
      return null
    },
    extension() {
      if (this.selectedCount === 1) {
          let extension = this.selected[0].extension
          if (extension) return extension.replace(".", "")

      }
      return null

    },
    inTrashSince() {
      if (this.selectedCount === 0) {
        return this.currentFolder.in_trash_since

      }
      else if (this.selectedCount === 1) {
        return this.selected[0].in_trash_since
      }
      return null

    },
    owner() {
      if (this.selectedCount === 0) {
          return this.currentFolder.owner?.name

      }
      else if (this.selectedCount === 1) {
          return this.selected[0].owner?.name
      }
      return null
    },
    isDir() {
      if (this.selectedCount === 1) {

        return this.selected[0].isDir
      }
      return true

    },

    folderItemsCount() {
        let folder
        if (this.selectedCount === 0 && this.currentFolder) {
            folder = this.currentFolder
        } else if (this.selectedCount === 1) {
            if (this.selected[0].isDir) {
                folder = this.selected[0]
            }
        }
        if (folder) {
          let numFolders = folder.numFolders
          let numFiles  = folder.numFiles
          return {numFolders, numFiles}

        }

    },

  },
  methods: {
    humanSize(size) {
        return filesize(size)
    },
    humanTime(date) {
      if (this.settings.dateFormat) {
        return moment(date, "YYYY-MM-DD HH:mm").format("DD/MM/YYYY, hh:mm")
      }
      //todo czm globalny local nie dzIała?
      let locale = this.settings?.locale || "en"

      moment.locale(locale)
      // Parse the target date
      return moment(date, "YYYY-MM-DD HH:mm").endOf('second').fromNow()

    },

    changeView: async function (event, type) {
        if (event.target.innerHTML.toString().includes("bytes")) {
            if (type === "size") {
                event.target.innerHTML = this.humanSize(this.size)
            }
            else if (type === "encryptedSize"){
                event.target.innerHTML = this.humanSize(this.encryptedSize)
            }
        }
        else {
            if (type === "size") {
                event.target.innerHTML = this.size + " bytes"
            }
            else if (type === "encryptedSize"){
                event.target.innerHTML = this.encryptedSize + " bytes"
            }

        }

    },
  },
}
</script>
<style lang="css" scoped>
.checkmark-true:after {
    content: "\002705";
 color: #2ecc71;

 margin-left: 5px; /* Adjust the margin value based on your preference */
    /* Add other styles for the green checkmark icon if needed */
}


.checkmark-false:after {
 content: "\00274C";
 color: #d31010;

 margin-left: 5px; /* Adjust the margin value based on your preference */
 /* Add other styles for the green checkmark icon if needed */
}
</style>
