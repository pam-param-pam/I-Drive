<template>
  <div
    v-if="filesInUploadCount > -1"
    class="upload-files"
    v-bind:class="{ closed: !open }"
  >
    <div class="card floating">
      <div class="card-title">
        <h2>{{ $t("prompts.uploadFiles", { files: filesInUploadCount }) }}</h2>
        <div class="upload-info">
          <div class="upload-speed">{{ uploadSpeed.toFixed(2) }} MB/s</div>
          <div class="upload-eta">{{ formattedETA }} remaining</div>
        </div>
        <button
          class="action"
          @click="abortAll"
          aria-label="Abort upload"
          title="Abort upload"
        >
          <i class="material-icons">{{ "cancel" }}</i>
        </button>
        <button
          class="action"
          @click="toggle"
          aria-label="Toggle file upload list"
          title="Toggle file upload list"
        >
          <i class="material-icons">{{
            open ? "keyboard_arrow_down" : "keyboard_arrow_up"
          }}</i>
        </button>
      </div>
      <div class="card-content">
        <UploadFile
          v-for="file in filesssss"
          :key="file.name"
          :file="file"
          :data-dir="file.isDir"
          :data-type="file.type"
          :aria-label="file.name"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters, mapMutations } from "vuex"
import buttons from "@/utils/buttons"
import UploadFile from "@/components/UploadFile.vue"

export default {
  name: "uploadFiles",
  components: {UploadFile},
  data: function () {
    return {
      open: false,
      filesssss: [{name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},
        {name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},
        {name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},
        {name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},
        {name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},
        {name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},
        {name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},
        {name:"saaa.webm", "id": "aaa", "size": 123, "status": "uploading", "percentage": 70, "isDir": false, "type": "movie"},
        {name:"bbbb.text", "id": "aaa", "size": 123, "status": "uploading", "percentage": 30, "isDir": false, "type": "movie"},
        {name:"cccc.mp4", "id": "aaa", "size": 123, "status": "uploading", "percentage": 20, "isDir": false, "type": "movie"},]
    }
  },
  computed: {
    ...mapGetters(["filesInUpload", "filesInUploadCount", "uploadSpeed", "eta"]),
    ...mapMutations(["resetUpload"]),
    formattedETA() {
      if (!this.eta || this.eta === Infinity) {
        return "--:--:--"
      }

      let totalSeconds = this.eta
      const hours = Math.floor(totalSeconds / 3600)
      totalSeconds %= 3600
      const minutes = Math.floor(totalSeconds / 60)
      const seconds = Math.round(totalSeconds % 60)

      return `${hours.toString().padStart(2, "0")}:${minutes
        .toString()
        .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`
    },
  },
  methods: {
    toggle: function () {
      this.open = !this.open
    },
    abortAll() {
      if (confirm(this.$t("upload.abortUpload"))) {
        abortAllUploads()
        buttons.done("upload")
        this.open = false
        this.$store.commit("resetUpload")
        this.$store.commit("setReload", true)
      }
    },
  },
}
</script>
