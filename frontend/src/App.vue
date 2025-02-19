<template>
   <router-view></router-view>
</template>

<script>
export default {
   name: 'app',

   mounted() {
      const loading = document.getElementById('loading')
      loading.classList.add('done')

      setTimeout(() => {
         loading.parentNode.removeChild(loading)
      }, 200)
   }
}
</script>

<style>
@import './css/styles.css';

html,
body,
#app {
   height: 100%;
}

body {
   overflow: hidden;
}

body.enable-scroll,
#app.enable-scroll {
   overflow: auto !important;
}
</style>
