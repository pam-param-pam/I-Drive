<template>
  <div>
    <video ref="videoPlayer" controls @timeupdate="handleTimeUpdate"></video>
  </div>
</template>

<script>
import {fetchJSON} from "@/api/utils.js";

export default {
  data() {
    return {
      videoFragments: [],
      decryptionKey: '',
      currentIndex: 0,
      downloading: false,
    };
  },
  mounted() {
    this.fetchVideoManifest();
  },
  methods: {
    async fetchVideoManifest() {
      // Fetch JSON manifest
      let fileId = this.$route.params.fileId;
      const response = await fetchJSON('/api/fragments/' + fileId);

      // Extract decryption key and fragments
      this.decryptionKey = response.Decryption_key;
      this.videoFragments = response.fragments;

      // Start playing video
      this.playVideo();
    },
    async playVideo() {
      this.$refs.videoPlayer.src = await this.getNextFragment();
      //this.$refs.videoPlayer.play();
    },
    async getNextFragment() {
      if (this.currentIndex >= this.videoFragments.length) return; // All fragments fetched

      const fragment = this.videoFragments[this.currentIndex];
      const response = await fetch(fragment.url);
      const chunk = await response.arrayBuffer();

      // Decrypt chunk if necessary
      // (Use your decryption logic here)
      this.currentIndex++;

      return URL.createObjectURL(new Blob([chunk], { type: 'video/mp4' }));
    },
    async handleTimeUpdate() {
      const video = this.$refs.videoPlayer;
      if (video.currentTime > video.duration * 0.8 && !this.downloading) {
        // Start downloading next fragment when video is close to 80% completion
        this.downloading = true;
        const nextFragmentUrl = await this.getNextFragment();
        if (nextFragmentUrl) {
          video.src = nextFragmentUrl;
          await video.play();
        }
        this.downloading = false;
      }
    },
  },
};
</script>
