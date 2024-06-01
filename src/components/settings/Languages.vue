<template>
  <select v-on:change="change" :value="locale">
    <option v-for="(language, value) in locales" :key="value" :value="value">
      {{ $t("languages." + language) }}
    </option>
  </select>
</template>

<script>
export default {
  name: "languages",
  props: ["locale"],
  data() {
    let dataObj = {
      locales: {
        en: "en",
        pl: "pl",
        uwu: "uwu",

      },
    }

    Object.defineProperty(dataObj, "locales", {
      configurable: false,
      writable: false,
    })

    return dataObj
  },
  methods: {
    change(event) {
      this.$emit("update:locale", event.target.value)
    },
  },
}
</script>
