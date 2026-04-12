<template>
   <div v-if="loading">
      <h2 class="message delayed">
         <div class="spinner">
            <div class="bounce1"></div>
            <div class="bounce2"></div>
            <div class="bounce3"></div>
         </div>
         <span v-if="showText">{{ $t("files.loading") }}</span>
      </h2>
   </div>
</template>

<script>

export default {
   name: "loadingSpinner",
   props: {
      loading: Boolean,
      showText: {
         type: Boolean,
         required: false,
         default: true
      }
   },

}

</script>

