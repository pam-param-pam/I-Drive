<template>
  <div
    class="fileitem-wrapper"
    :class="{
      'failed-border': file.status === 'failed',
      'success-border': file.status === 'success',
      'paused-border': file.status === 'paused',
      'uploading-border': file.status === 'uploading',
      'shake-animation': isShaking,
    }"
  >
    <!-- Upper -->
    <div class="fileitem-header">
      <span class="file-name">{{ file.name }}</span>
      <div class="button-group">
        <button class="pause-button" @click="togglePause">
          <i class="material-icons">{{ file.status === 'paused' ? 'play_arrow' : 'pause' }}</i>
        </button>
        <button
          class="cancel-button"
          @mouseover="startShake"
          @mouseleave="stopShake"
          @click="cancel"
        >
          <i class="material-icons">close</i>
        </button>
      </div>
    </div>

    <!-- Lower -->
    <div v-if="file.progress">
      <span v-if="file.status === 'creating'">
        <b class="creating">{{ $t('uploadFile.creating') }}</b>
      </span>
      <span v-if="file.status === 'failed'">
        <b class="failed">{{ $t('uploadFile.failed') }}</b>
      </span>
      <span v-if="file.status === 'success'">
        <b class="success">{{ $t('uploadFile.success') }}</b>
      </span>
      <span v-if="file.status === 'paused'">
        <b class="paused">{{ $t('uploadFile.paused') }}</b>
      </span>
      <span v-if="file.status === 'pausing'">
        <b class="pausing">{{ $t('uploadFile.pausing') }}</b>
      </span>
      <div class="fileitem-progress">
        <ProgressBar
          v-if="file.status === 'uploading'"
          :progress="file.progress"
        />
        <span v-if="file.status === 'uploading'">
          <b> {{ file.progress }}% </b>
        </span>
      </div>
    </div>
  </div>
</template>

<script>
import ProgressBar from "@/components/ProgressBar.vue"
import {mapMutations} from "vuex"

export default {
  components: { ProgressBar },
  props: ["file"],
  data() {
    return {
      isPaused: false,
      isShaking: false,


    }
  },
  computed: {
    ...mapMutations([])
  },
  methods: {
    togglePause() {
      this.file.status = this.file.status === "uploading" ? "paused" : "uploading"
    },
    cancel() {
      this.$store.commit("upload/cancelJob", this.file.id)

    },
    startShake() {
      this.isShaking = true
    },
    stopShake() {
      this.isShaking = false
    },
  },
}
</script>

<style scoped lang="scss">
.fileitem-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  border: 0.15em dashed lightgray;
  border-radius: 0.5rem;
  padding: 0.5rem;
  margin-bottom: 0.4em;

}

.fileitem-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.file-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fileitem-progress {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.failed {
  color: red;
}

.success {
  color: green;
}
.paused {
  color: orange;
}

.failed-border {
  border-color: red;
}
.uploading-border {

}
.success-border {
  border-color: green;
}
.paused-border {
  border-color: orange;
}

.button-group {
  display: flex;
  gap: 0.5rem;
}

.cancel-button, .pause-button {
  background: none;
  border: none;
  padding: 0;
  margin: 0;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.3s;
}

.pause-button:hover {
  background-color: #eeeeee;
}

.cancel-button:hover {
  background-color: #eeeeee;
  color: red;

}

.material-icons {
  font-size: 22px;
  vertical-align: middle;
}


@keyframes shake {
  0% { transform: translate(0, 0); }
  17% { transform: translate(-1px, -1px); }
  34% { transform: translate(1px, -1px); }
  51% { transform: translate(-1px, 1px); }
  68% { transform: translate(1px, 1px); }
  85% { transform: translate(-1px, -1px); }
  100% { transform: translate(0, 0); }
}

.shake-animation {
  animation: shake 0.3s ease infinite; /* Make the animation run infinitely */
  border-color: red;

}
</style>
