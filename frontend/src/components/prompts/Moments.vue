<template>
  <div class="card floating moments-popup">
    <div class="card-title">
      <h2>{{ $t("prompts.momentsTitle") }}</h2>
    </div>

    <div class="card-content" :class="{ 'vertical': isMobile() }">

      <!-- Left Section: Current Video Frame -->
      <div class="left-section">
        <img :src="currentThumbnailURL" class="current-thumbnail" alt="Current Preview" />
        <span class="current-time">{{ formatTime(currentTimestamp) }}</span>
        <button
          :aria-label="$t('buttons.addMoment')"
          :title="$t('buttons.addMoment')"
          class="button button--flat"
          @click="addMoment"
        >
          <span>{{ $t("buttons.addMoment") }}</span>
        </button>
      </div>
      <div v-if="moments.length === 0">
         <span>
           <h3> {{ $t("prompts.momentsTip") }}</h3>
         </span>
      </div>
      <!-- Right Section: List of Moments -->
      <div v-else class="moments-list" :class="{ 'vertical': isMobile() }">
        <div
          v-for="(moment, index) in sortedMoments"
          :key="index"
          class="moment-wrapper"
        >
          <div class="thumbnail-container">
            <img :src="moment.url" class="moment-thumbnail" alt="Moment Preview" />
            <!-- Play button that shows on hover -->
            <button
              class="play-button"
              @click="playMoment(moment)"
              aria-label="Play Moment"
              title="Play Moment"
            >
              <i class="material-icons">play_arrow</i>
            </button>
          </div>

          <span class="moment-time">Starts at: {{ formatTime(moment.timestamp) }}</span>

          <button
            :aria-label="$t('buttons.delete')"
            :title="$t('buttons.delete')"
            class="action"
            @click="deleteMoment($event, moment)"
          >
            <i class="material-icons">delete</i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { captureVideoFrame, generateIv, generateKey, upload } from "@/utils/uploadHelper.js"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { isMobile } from "@/utils/common.js"
import { addMoment, getMoments, removeMoment } from "@/api/files.js"
import { canUpload } from "@/api/user.js"
import { encrypt } from "@/utils/encryption.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import throttle from "lodash.throttle"

export default {
   name: "moments",
   props: {
      video: {
         type: HTMLVideoElement,
         required: true
      }
   },
   data() {
      return {
         moments: [],
         currentThumbnailURL: null,
         currentThumbnailData: null

      }
   },
   async mounted() {
      this.currentThumbnailURL = await this.getCurrentThumbnail()
      await this.fetchData()
   },
   computed: {
      ...mapState(useMainStore, ["selected"]),
      ...mapState(useUploadStore, ["attachmentName"]),

      currentTimestamp() {
         return this.video?.currentTime || 0
      },

      sortedMoments() {
         return [...this.moments].sort((a, b) => a.timestamp - b.timestamp)
      },
      file() {
         return this.selected[0]
      }
   },
   methods: {
      isMobile() {
         return isMobile()
      },
      ...mapActions(useMainStore, ["closeHover"]),
      async fetchData() {
         this.moments = await getMoments(this.file.id)
      },
      addMoment: throttle(async function() {
         let timestamp = Math.floor(this.currentTimestamp)
         if (this.moments.some(moment => moment.timestamp === timestamp)) {
            this.$toast.error(this.$t("toasts.momentAlreadyExists"))
            return
         }
         this.$toast.info(this.$t("toasts.savingMoment"))

         let res = await canUpload(this.file.parent_id)
         if (!res.can_upload) {
            return
         }
         let fileFormList = new FormData()

         let method = this.file.encryption_method
         let iv = generateIv(method)
         let key = generateKey()
         let encryptedBlob = await encrypt(this.currentThumbnailData, method, key, iv, 0)

         fileFormList.append("file", encryptedBlob, this.attachmentName)

         let uploadResponse = await upload(fileFormList, {})
         let moment_data = {
            timestamp: timestamp,
            file_id: this.file.id,
            size: encryptedBlob.size,
            message_id: uploadResponse.data.id,
            attachment_id: uploadResponse.data.attachments[0].id,
            iv: iv,
            key: key,
            message_author_id: uploadResponse.data.author.id
         }
         let moment = await addMoment(moment_data)
         if (moment) {
            this.moments.push(moment)
         }
      }, 1000),
      async deleteMoment(event, moment) {
         await removeMoment({ "file_id": this.file.id, "timestamp": moment.timestamp })
         this.moments = this.moments.filter(m => m !== moment)
         this.$toast.info(this.$t("toasts.momentRemoved"))

      },
      formatTime(seconds) {
         let minutes = Math.floor(seconds / 60)
         let secs = Math.floor(seconds % 60)
         return `${minutes}:${secs < 10 ? "0" : ""}${secs}`
      },
      async playMoment(moment) {
         this.video.currentTime = moment.timestamp
         //don't ask me why u have to call play() twice
         await this.video.play()
         this.cancel()
      },
      async getCurrentThumbnail() {

         if (this.video) {
            let data = await captureVideoFrame(this.video, this.currentTimestamp)
            this.currentThumbnailData = data.thumbnail
            return URL.createObjectURL(data.thumbnail)

         }
      },
      cancel() {
         this.closeHover()
         this.video.play()
      }
   }
}
</script>

<style scoped>

.card.floating {
 max-height: 60vh;
}

.card-content.vertical {
 flex-direction: column;
 align-items: center;
}

h3 {
 min-width: 10em;
 padding-right: 2em;
 display: block;
 overflow: hidden;
 line-height: 1.5em;
}

.moments-popup {
 display: flex;
 flex-direction: column;
 max-width: 100vh !important;
 padding: 15px;
 background: white;
 min-height: 21em;
 border-radius: 8px;
 box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.card-content {
 display: flex;
 gap: 20px;
 user-select: none;
}

.left-section {
 display: flex;
 flex-direction: column;
 align-items: center;
 gap: 10px;
 padding: 10px;
 border-radius: 8px;
}

.current-thumbnail {
 width: 250px;
 height: 120px;
 border-radius: 5px;
}

.current-time {
 font-size: 16px;
 font-weight: bold;
}

.moments-list {
 display: flex;
 gap: 10px;
 overflow-x: auto;
 width: 100%;
 padding-bottom: 10px;
}

.moments-list.vertical {
 flex-direction: column;
 overflow: hidden;
 max-height: 70vh;
}

.moment-wrapper {
 display: flex;
 flex-direction: column;
 align-items: center;
 cursor: pointer;
 padding-bottom: 1em;
 position: relative;

}

.vertical .action {
 margin: 0 !important;
 padding: 0 !important;
}

.action {
 margin-top: 1em;
}

.moment-thumbnail {
 width: 200px;
 height: 100px;
 min-height: 100px;
 min-width: 200px;
 border-radius: 5px;
 background: var(--surfaceSecondary);
}

.moment-time {
 font-size: 16px;
 font-weight: bold;
 margin-top: 15px;
}


.thumbnail-container {
 position: relative;
}

.moment-thumbnail {
 width: 200px;
 height: 100px;
 border-radius: 5px;
 object-fit: cover;
}

.play-button {
 position: absolute;
 top: 0;
 left: 0;
 width: 100%;
 height: 100%;
 background-color: rgba(0, 0, 0, 0.5);
 color: white;
 border: none;
 display: none;
 justify-content: center;
 align-items: center;
 cursor: pointer;
}

.play-button i {
 font-size: 48px;
}

.play-button:hover {
 opacity: 0.7;
}

.thumbnail-container:hover .play-button {
 display: flex;
}
</style>
