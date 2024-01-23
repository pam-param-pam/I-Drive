<template>
  <video ref="video" width="100%" height="640" controls></video>
</template>

<script>
import Hls from 'hls.js';
import store from "@/store/index.js";
import {baseURL} from "@/utils/constants.js";

export default {
  mounted() {
    let hls = new Hls({
      xhrSetup: xhr => {
        xhr.setRequestHeader('Authorization', `Token ${store.state.token}`)
        xhr.setRequestHeader('Origin', `https://discord.com/`)
        xhr.setRequestHeader('Referer', `https://discord.com/`)

      }
    })

    let stream = baseURL +  '/api/stream/caa8cddb-e44b-4e5d-8a95-2b58a8524d08'
    let video = this.$refs["video"];
    hls.loadSource(stream);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, function () {
      video.play();
    });
  },
};
</script>