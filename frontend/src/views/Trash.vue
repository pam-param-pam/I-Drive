<template>

</template>

<script>

import {mapMutations} from "vuex";

export default {
  name: "Trash",
  methods: {
    ...mapMutations(["setIsTrash"])
  },
  created() {
    this.setIsTrash(true)
  },
  beforeDestroy() {
    this.setIsTrash(false)

  }

}

</script>

<style scoped>

</style>