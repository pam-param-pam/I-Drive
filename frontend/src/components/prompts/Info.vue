<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.itemInfo") }}</h2>
    </div>

    <div v-if="!isFileExpanded" class="card-content">
      <p v-if="selected.length > 1">
        {{ $t("prompts.itemsSelected", { count: selected.length }) }}
      </p>

      <p v-if="name" class="break-word">
        <strong>{{ $t("prompts.displayName") }}:</strong> {{ name }}
      </p>

      <p v-if="id" class="break-word">
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

      <p v-if="size != null">
        <strong>{{ $t("prompts.size") }}: </strong>
        <code @dblclick="changeView($event, size, humanSize, ' bytes')">
          {{ humanSize(size) }}
        </code>
      </p>

      <p v-if="encryptionMethod">
        <strong>{{ $t("settings.encryptionMethod") }}:</strong> {{ $t(encryptionMethod) }}
        <span v-if="is_encrypted" class="checkmark-true"></span>
        <span v-else class="checkmark-false"></span>
      </p>

      <p v-if="owner">
        <strong>{{ $t("prompts.owner") }}:</strong> {{ owner }}
      </p>

      <div v-if="resolution">
        <strong>{{ $t("prompts.resolution") }}:</strong>
        {{ resolution.width }} x {{ resolution.height }}
      </div>
      <div v-if="duration">
        <strong>{{ $t("prompts.duration") }}:</strong> {{ formatSeconds(duration) }}
      </div>
      <p v-if="created">
        <strong>{{ $t("prompts.created") }}:</strong> {{ humanTime(created) }}
      </p>
      <p v-if="last_modified">
        <strong>{{ $t("prompts.lastModified") }}:</strong> {{ humanTime(last_modified) }}
      </p>
      <p v-if="crc">
        <strong>{{ $t("prompts.crc32") }}: </strong>
        <code @dblclick="changeView($event, crc, formatCrc)">
          {{ formatCrc(crc) }}
        </code>
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

      <!-- Expandable section -->
      <div v-if="isDir && !isInShareContext" class="expandable-section">
        <div class="expandable-header" @click="fetchAdditionalInfo">
          <strong>{{ $t("prompts.fetchMoreInfo") }}</strong>
          <i :class="{ expanded: isFolderExpanded }" class="material-icons expand-icon">
            keyboard_arrow_down
          </i>
        </div>

        <div v-if="isFolderExpanded" class="expandable-content">
          <p>
            <strong>{{ $t("prompts.numberDirs") }}:</strong> {{ numberDirs }}
          </p>
          <p>
            <strong>{{ $t("prompts.numberFiles") }}:</strong> {{ numberFiles }}
          </p>
          <p v-if="folderSize != null">
            <strong>{{ $t("prompts.size") }}: </strong>
            <code @dblclick="changeView($event, folderSize, humanSize, ' bytes')">
              {{ humanSize(folderSize) }}
            </code>
          </p>
        </div>
      </div>
    </div>
    <!-- Expandable section for tracks -->
    <div v-if="!isDir && type==='Video' && isVideoMetadata && !isInShareContext" class="expandable-section card-content">
      <div class="expandable-header" @click="fetchAdditionalInfo">
        <strong>{{ $t("prompts.videoMetadata") }}</strong>
        <i :class="{ expanded: isFileExpanded }" class="material-icons expand-icon">
          keyboard_arrow_down
        </i>
      </div>

      <div v-if="isFileExpanded" class="expandable-content">
        <div v-if="metadata">
          <div v-if="primaryMetadata">
            <p>
              <strong>{{ $t("prompts.codec") }}:</strong> {{ primaryMetadata.codec }}
            </p>
            <p>
              <strong>{{ $t("prompts.resolution") }}:</strong> {{ primaryMetadata.resolution }}
            </p>
            <p>
              <strong>{{ $t("prompts.audioType") }}: </strong>
              <span v-if="primaryMetadata.audioType">
                 {{ primaryMetadata.audioType }}
              </span>
              <span v-else>
                {{ $t("prompts.noAudio") }}
              </span>
            </p>
            <p>
              <strong>{{ $t("prompts.isSubs") }}: </strong>
              <span v-if="primaryMetadata.isSubs">
                {{ $t("prompts.isSubsYes") }}
              </span>
              <span v-else>
                {{ $t("prompts.isSubsNo") }}
              </span>
            </p>
          </div>

          <select v-model="currentTrack" class="input input--block styled-select">
            <option v-for="track in metadata.tracks" :key="track" :value="track">{{ track.number }} - {{ track.type }} {{ $t("prompts.track") }}</option>
          </select>
          <div v-if="currentTrack">
            <p v-if="currentTrack?.codec">
              <strong>{{ $t("prompts.codec") }}:</strong> {{ currentTrack.codec }}
            </p>
            <p v-if="currentTrack?.bitrate">
              <strong>{{ $t("prompts.bitrate") }}:</strong> {{ currentTrack.bitrate }}
            </p>
            <p v-if="currentTrack?.height && currentTrack?.width">
              <strong>{{ $t("prompts.resolution") }}:</strong> {{ currentTrack.width }} x {{ currentTrack.height }}
            </p>
            <p v-if="currentTrack?.fps">
              <strong>{{ $t("prompts.fps") }}:</strong> {{ currentTrack.fps }}
            </p>
            <p v-if="currentTrack?.duration">
              <strong>{{ $t("prompts.duration") }}:</strong> {{ formatSeconds(currentTrack.duration) }}
            </p>
            <p v-if="currentTrack?.size">
              <strong>{{ $t("prompts.size") }}:</strong> {{ currentTrack.size }}
            </p>
            <p v-if="currentTrack?.sample_rate">
              <strong>{{ $t("prompts.sampleRate") }}:</strong> {{ currentTrack.sample_rate }}
            </p>
            <p v-if="currentTrack?.channel_count">
              <strong>{{ $t("prompts.channelCount") }}:</strong> {{ currentTrack.channel_count }}
            </p>
            <p v-if="currentTrack?.sample_size">
              <strong>{{ $t("prompts.sampleSize") }}:</strong> {{ currentTrack.sample_size }}
            </p>
            <p v-if="currentTrack?.language">
              <strong>{{ $t("prompts.language") }}:</strong> {{ currentTrack.language }}
            </p>
          </div>

        </div>
      </div>
    </div>
    <div class="card-action">
      <button
        :aria-label="$t('buttons.ok')"
        :title="$t('buttons.ok')"
        class="button button--flat"
        type="submit"
        @click="closeHover()"
      >
        {{ $t("buttons.ok") }}
      </button>
    </div>
  </div>
</template>

<script>
import { filesize } from "@/utils"
import { fetchAdditionalInfo } from "@/api/item.js"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import { encryptionMethod, encryptionMethods } from "@/utils/constants.js"
import { formatSeconds, humanTime } from "@/utils/common.js"

export default {
   name: "info",

   data() {
      return {
         numberDirs: "Loading...",
         numberFiles: "Loading...",
         folderSize: "Loading...",
         currentTrack: null,
         isFolderExpanded: false,
         isFileExpanded: false,
         metadata: null
      }
   },

   computed: {
      ...mapState(useMainStore, ["selected", "settings", "currentFolder", "selectedCount", "isLogged"]),
      isMoreDataFetched() {
         return this.folderSize !== "Loading..."
      },
      isInShareContext() {
         return !this.isLogged
      },
      size() {
         if (this.selectedCount === 1 && !this.selected[0].isDir) {
            return this.selected[0].size
         }
         if (this.selectedCount > 1) {
            let sum = 0
            for (let selected of this.selected) {
               if (!selected.isDir) sum += selected.size
            }
            return sum
         }
         return null
      },

      name() {
         if (this.selectedCount === 0) {
            return this.currentFolder.name
         } else if (this.selectedCount === 1) {
            return this.selected[0].name
         }
         return null
      },

      encryptionMethod() {
         if (this.selectedCount === 1) {
            if (this.selected[0].isDir) return null
            return encryptionMethods[this.selected[0].encryption_method]
         }
         return null
      },
      created() {
         if (this.selectedCount === 0) {
            return this.currentFolder.created
         } else if (this.selectedCount === 1) {
            return this.selected[0].created
         }
         return null
      },
      last_modified() {
         if (this.selectedCount === 0) {
            return this.currentFolder.last_modified
         } else if (this.selectedCount === 1) {
            return this.selected[0].last_modified
         }
         return null
      },
      id() {
         if (this.selectedCount === 0) {
            return this.currentFolder.id
         } else if (this.selectedCount === 1) {
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

      is_encrypted() {
         if (this.selectedCount === 1) {
            if (this.selected[0].isDir) return null
            return this.selected[0].encryption_method !== encryptionMethod.NotEncrypted
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
            const filename = this.selected[0].name
            if (filename && filename.includes(".")) {
               return filename.split(".").pop().toLowerCase()
            }
         }
         return null
      },
      inTrashSince() {
         if (this.selectedCount === 0) {
            return this.currentFolder.in_trash_since
         } else if (this.selectedCount === 1) {
            return this.selected[0].in_trash_since
         }
         return null
      },
      duration() {
         if (this.selectedCount === 1) {
            return this.selected[0].duration
         }
         return null
      },
      owner() {
         if (this.selectedCount === 0) {
            return this.currentFolder.owner
         } else if (this.selectedCount === 1) {
            return this.selected[0].owner
         }
         return null
      },
      isDir() {
         if (this.selectedCount === 0) {
            return this.currentFolder.isDir
         }
         if (this.selectedCount === 1) {
            return this.selected[0].isDir
         }

         return false
      },
      isVideoMetadata() {
         if (this.selectedCount === 1) {
            return this.selected[0].isVideoMetadata
         }
         return false
      },
      crc() {
         if (this.selectedCount === 1) {
            if (!this.selected[0].isDir) {
               return this.selected[0].crc
            }
         }
         return null
      },
      primaryMetadata() {
         if (!this.metadata) return
         let primary = {}
         let videoTrack = this.metadata.tracks.filter(track => track.type === "Video")?.[0]
         let audioTrack = this.metadata.tracks.filter(track => track.type === "Audio")?.[0]
         let subsLength = this.metadata.tracks.filter(track => track.type === "Subtitle")?.length

         const codecMap = {
            "avc1": "H.264",
            "hev1": "H.265 (HEVC)",
            "hvc1": "H.265 (HEVC)",
            "vp09": "VP9",
            "av01": "AV1",
            "mp4a": "AAC"
         }
         if (videoTrack?.codec) {
            let codecPrefix = videoTrack.codec.split(".")[0]
            primary.codec = codecMap[codecPrefix] || `Unknown (${videoTrack?.codec})`
         }
         primary.resolution = videoTrack.width + " x " + videoTrack.height
         primary.audioType = audioTrack ? (audioTrack.channel_count > 1 ? "Stereo" : "Mono") : "No audio"
         primary.isSubs = subsLength > 0
         return primary
      }
   },

   methods: {
      humanTime,
      formatSeconds,

      ...mapActions(useMainStore, ["closeHover"]),

      async fetchAdditionalInfo() {
         let item
         if (this.selectedCount === 0) item = this.currentFolder
         else item = this.selected[0]

         // we want to fetch data only once
         if (this.isMoreDataFetched) {
            if (item.isDir) {
               this.isFolderExpanded = !this.isFolderExpanded
            } else {
               this.isFileExpanded = !this.isFileExpanded
            }
            return
         }

         let res = await fetchAdditionalInfo(item.id)
         if (item.isDir) {
            this.folderSize = res.folder_size
            this.numberDirs = res.folder_count
            this.numberFiles = res.file_count
            this.isFolderExpanded = !this.isFolderExpanded
         } else {
            this.metadata = res
            this.isFileExpanded = !this.isFileExpanded

         }
      },

      humanSize(size) {
         return filesize(size)
      },
      formatCrc(crc) {
         return "0x" + crc.toString(16).toUpperCase()
      },

      async changeView(event, rawValue, formatFn, suffix = "") {
         let pretty = formatFn(rawValue).toString()
         let raw = rawValue.toString() + suffix
         let current = event.target.innerText.trim()

         event.target.innerText = current === pretty ? raw : pretty

         await navigator.clipboard.writeText(rawValue.toString())
         this.$toast.success(this.$t("toasts.copied"))
      }
   }
}
</script>
<style scoped>
.checkmark-true:after {
 content: '\002705';
 color: #2ecc71;
 margin-left: 5px;
}

.checkmark-false:after {
 content: '\00274C';
 color: #d31010;
 margin-left: 5px;
}
</style>
