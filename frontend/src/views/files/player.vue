<template>
  <video ref="video" width="100%" height="640" controls></video>
</template>

<script>
import Hls from 'hls.js';
import store from "@/store/index.js";
import {baseURL} from "@/utils/constants.js";

export default {
  mounted() {
    let url = this.$route.path;

    let item_id = url.replace("/files/player/", "")

    let hls = new Hls({
      xhrSetup: xhr => {
        xhr.setRequestHeader('Authorization', `Token ${store.state.token}`)
        xhr.setRequestHeader('Origin', `https://discord.com/`)
        xhr.setRequestHeader('Referer', `https://discord.com/`)

      }
    })

    let stream = baseURL +  `/api/stream/${item_id}`
    let video = this.$refs["video"];
    hls.loadSource("http://127.0.0.1:8000/api/teststream");
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, function () {
      video.play();
    });
  },
};
</script>