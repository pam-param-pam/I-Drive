<template>
  <div class="progress-wrapper">
    <div class="progress" :style="{ width: progress + '%' }">
      <div class="stripe"></div> <!-- Add the stripe -->

    </div>
  </div>
</template>

<script>
export default {
  props: ["progress"],
}
</script>

<style scoped lang="scss">
.progress-wrapper {
  width: 100%;
  height: 1rem;
  padding: 0.2rem;
  background-color: rgb(235, 235, 235);
  border-radius: 0.5rem;
  overflow: hidden; /* Ensure overflow is hidden */
  z-index: -1;

}

.progress {
  position: relative;
  height: 100%;
  background: rgb(0, 157, 255);
  border-radius: 0.5rem;
}

.stripe {
  position: absolute;
  top: 0;
  left: 0;
  width: 200%; /* Make the stripe wider for diagonal effect */
  height: 100%;
  background: linear-gradient(135deg, rgba(173, 216, 230, 0.7), rgba(173, 216, 230, 0)); /* Light blue gradient */
  transform: rotate(-60deg); /* Rotate the stripe */
  animation: moveStripe 2s linear infinite; /* Animation */

}

@keyframes moveStripe {
  0% { left: -100%; } /* Start position */
  100% { left: 100%; } /* End position */
}
</style>