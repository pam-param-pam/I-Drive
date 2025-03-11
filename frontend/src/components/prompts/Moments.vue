<template>
  <div class="card floating moments-popup">
    <div class="card-title">
      <h2>{{ $t("moments.title") }}</h2>
    </div>

    <div class="card-content">

      <!-- Left Section: Current Video Frame -->
      <div class="left-section">
        <img :src="currentThumbnail" class="current-thumbnail" alt="Current Preview" />
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
           <h3> Save moments you'd like to rewatch later! </h3>
         </span>
      </div>
      <!-- Right Section: List of Moments -->
      <div v-else class="moments-list">
        <div
          v-for="(moment, index) in sortedMoments"
          :key="index"
          class="moment-wrapper"
        >
          <div class="moment-item moment-wrapper">
            <img :src="moment.thumbnail" class="moment-thumbnail" alt="Moment Preview" />
            <span class="moment-time">Starts at: {{ formatTime(moment.timestamp) }}</span>
          </div>

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
import { captureVideoFrame } from "@/utils/uploadHelper.js"
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "moments",
   props: {
      video: {
         type: HTMLVideoElement,
         required: true // Ensure video object is provided
      }
   },
   data() {
      return {
         moments: [],
         currentThumbnail: null,
      }
   },
   async mounted() {
     this.currentThumbnail = await this.getCurrentThumbnail()
   },
   computed: {

      currentTimestamp() {
         return this.video?.currentTime || 0 // Default to 0 if undefined
      },

      sortedMoments() {
         return [...this.moments].sort((a, b) => a.timestamp - b.timestamp)
      }
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      addMoment() {
         let timestamp = this.currentTimestamp
         let thumbnail = this.currentThumbnail
         this.moments.push({ timestamp, thumbnail })
      },
      deleteMoment(event, moment) {

      },
      formatTime(seconds) {
         let minutes = Math.floor(seconds / 60)
         let secs = Math.floor(seconds % 60)
         return `${minutes}:${secs < 10 ? "0" : ""}${secs}`
      },
      async getCurrentThumbnail() {

         if (this.video) {
            let data = await captureVideoFrame(this.video, this.currentTimestamp)
            console.log(data)
            return URL.createObjectURL(data.thumbnail)

         }
      },
      cancel() {
         this.closeHover()
         this.video.play()
      },
   }
}
</script>

<style scoped>
.moments-popup {
 display: flex;
 flex-direction: column;
 max-width: 60em !important; /* Wider popup */
 padding: 15px;
 background: white;
 min-height: 21em;
 border-radius: 8px;
 box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.card-content {
 display: flex;
 gap: 20px;
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

.moment-wrapper {
 display: flex;
 flex-direction: column;
 align-items: center;
 cursor: pointer;
 transition: transform 0.2s ease-in-out;
 padding-bottom: 1em;
}

.moment-item:hover {
 transform: scale(1.05);
}

.action {
 margin-top: 1em;
}

.moment-thumbnail {
 width: 200px;
 height: 100px;
 border-radius: 5px;
}

.moment-time {
 font-size: 16px;
 font-weight: bold;
 margin-top: 15px;
}
</style>
