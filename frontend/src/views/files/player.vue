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

    let stream = `https://corsproxy.io/?` + encodeURIComponent(baseURL +  '/api/stream/514fd2a9-3f22-4fc0-b36e-e854b8d82a9d.m3u8');
    let video = this.$refs["video"];
    hls.loadSource(stream);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, function () {
      video.play();
    });
  },
};
</script>