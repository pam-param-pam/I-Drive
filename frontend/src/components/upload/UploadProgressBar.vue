<template>
   <div class="progress-wrapper">
      <div :style="{ width: progress + '%' }" class="progress">
         <div class="stripe"></div>
      </div>
   </div>
</template>

<script>
export default {
   name: 'UploadProgressBar',

   props: ['progress']
}
</script>

<style lang="scss" scoped>
.progress-wrapper {
   width: 100%;
   height: 1rem;
   padding: 0.2rem;
   background-color: rgb(235, 235, 235);
   border-radius: 0.5rem;
   overflow: hidden;
   z-index: -1;
}

.progress {
   position: relative;
   height: 100%;
   background: rgb(0, 157, 255);
   border-radius: 0.5rem;
   overflow: hidden;
}

.stripe {
   position: absolute;
   top: 0;
   left: 0;
   width: 200%;
   height: 100%;
   background: linear-gradient(135deg, rgba(173, 216, 230, 0.7), rgba(173, 216, 230, 0));
   transform: rotate(-60deg);
   animation: moveStripe 2s linear infinite;
}

@keyframes moveStripe {
   0% {
      left: -100%;
   }
   100% {
      left: 100%;
   }
}
</style>
