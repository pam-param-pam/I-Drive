<template>
   <div style="height: 100%">
      <img v-if="thumbSrc" :src="thumbSrc" class="cover" />

      <audio
         ref="audio"
         :autoplay="true"
         :src="src"
         controls
         @timeupdate="audioTimeUpdate"
         @error="onError"
      ></audio>

      <div class="seek-controls">
         <div class="seek-controls-inner">
            <div class="seek-controls-group seek-controls-group--backward">
               <button
                  v-for="seconds in seekIntervals"
                  :key="-seconds"
                  type="button"
                  :aria-label="$t('buttons.skipBackward', { amount: formatSeekInterval(seconds) })"
                  :title="$t('buttons.skipBackward', { amount: formatSeekInterval(seconds) })"
                  @click="seekBy(-seconds)"
               >
                  −{{ formatSeekInterval(seconds) }}
               </button>
            </div>
            <div class="seek-controls-group seek-controls-group--forward">
               <button
                  v-for="seconds in forwardSeekIntervals"
                  :key="seconds"
                  type="button"
                  :aria-label="$t('buttons.skipForward', { amount: formatSeekInterval(seconds) })"
                  :title="$t('buttons.skipForward', { amount: formatSeekInterval(seconds) })"
                  @click="seekBy(seconds)"
               >
                  +{{ formatSeekInterval(seconds) }}
               </button>
            </div>
         </div>
      </div>
   </div>
</template>

<script>
import { PreviewEvent } from "@/utils/constants.js"
import { backendInstance } from "@/axios/networker.js"

export default {
   props: ["file", "src", "thumbSrc", "mediaPosition"],
   emits: ["previewEvent", "error"],

   data() {
      return {
         lastSentMediaPosition: 0,
         audioRef: null,
         seekIntervals: [3600, 300, 60, 15]
      }
   },

   mounted() {
      this.audioRef = this.$refs.audio

      if (!this.audioRef) return
      this.audioRef.currentTime = this.mediaPosition || 0
      this.lastSentMediaPosition = this.mediaPosition || 0

   },

   watch: {
      mediaPosition() {
         if (this.mediaPosition) {
            this.audioRef.currentTime = this.mediaPosition
            this.lastSentMediaPosition = this.mediaPosition
         }
      }
   },

   computed: {
      forwardSeekIntervals() {
         return [...this.seekIntervals].reverse()
      }
   },

   methods: {
      formatSeekInterval(seconds) {
         if (seconds >= 3600) return `${seconds / 3600}h`
         if (seconds >= 60) return `${seconds / 60}m`
         return `${seconds}s`
      },
      seekBy(seconds) {
         if (!this.audioRef || !Number.isFinite(this.audioRef.currentTime)) return

         let target = Math.max(0, this.audioRef.currentTime + seconds)
         if (Number.isFinite(this.audioRef.duration)) {
            target = Math.min(target, this.audioRef.duration)
         }
         this.audioRef.currentTime = target
      },
      sendPreviewEvent(type, payload = {}) {
         this.$emit("previewEvent", {type, payload})
      },
      audioTimeUpdate() {
         if (!this.audioRef) return

         let position = Math.floor(this.audioRef.currentTime)

         if (Math.abs(position - this.lastSentMediaPosition) >= 10) {
            this.sendPreviewEvent(PreviewEvent.MEDIA_TIME_UPDATE, { timestamp: position })
            this.lastSentMediaPosition = position
         }
      },
      onError() {
         backendInstance.get(this.src, {
            headers: {
               Range: `bytes=0-1`
            },
            __skipAuth: true,
            baseURL: ""
         })
      }
   }
}
</script>

<style scoped>
.cover {
  max-width: 100%;
  max-height: 50%;
  display: block;
  margin: 0 auto;
}

.seek-controls {
  position: fixed;
  right: 0;
  bottom: 106px;
  z-index: 1;
  width: 100%;
  padding: 0 45px;
  box-sizing: border-box;
}

.seek-controls-inner {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
}

.seek-controls-group {
  display: flex;
  gap: 0.15rem;
  padding: 0.25rem;
  border: 1px solid rgba(127, 127, 127, 0.2);
  border-radius: 0.7rem;
  background: var(--surfacePrimary);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.14);
}

.seek-controls button {
  position: relative;
  flex: 0 0 auto;
  min-width: 3rem;
  min-height: 2rem;
  padding: 0.35rem 0.55rem;
  border: 0;
  border-radius: 0.45rem;
  background: transparent;
  color: var(--dark-blue);
  cursor: pointer;
  font: inherit;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  transition: background-color 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
}

.seek-controls button + button {
  margin-left: 0.2rem;
}

.seek-controls button + button::before {
  content: "";
  position: absolute;
  top: 0.4rem;
  bottom: 0.4rem;
  left: -0.28rem;
  width: 1px;
  background: rgba(127, 127, 127, 0.32);
  pointer-events: none;
}

.seek-controls button:hover {
  background: var(--surfaceSecondary);
}

.seek-controls button:focus-visible {
  box-shadow: inset 0 0 0 2px var(--dark-blue);
}

.seek-controls button:active {
  background: rgba(29, 153, 243, 0.18);
  transform: scale(0.96);
}

@media (max-width: 480px) {
  .seek-controls {
    padding: 0 0.5rem;
  }

  .seek-controls-inner {
    flex-direction: column;
    gap: 0.35rem;
  }

  .seek-controls-group {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.2rem;
  }

  .seek-controls button {
    min-width: 0;
    padding-right: 0.25rem;
    padding-left: 0.25rem;
  }

  .seek-controls button + button {
    margin-left: 0;
  }

  .seek-controls button + button::before {
    left: -0.11rem;
  }
}

@media (max-width: 240px) {
  .seek-controls {
    padding: 0 0.25rem;
  }

  .seek-controls button {
    padding: 0.25rem 0.1rem;
    font-size: 0.8rem;
  }
}
</style>
