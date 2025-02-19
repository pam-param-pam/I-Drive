<template>
   <select :value="locale" v-on:change="change">
      <option v-for="(language, value) in locales" :key="value" :value="value">
         {{ $t('languages.' + language) }}
      </option>
   </select>
</template>

<script>
export default {
   name: 'languages',

   props: ['locale'],

   emits: ['update:locale'],

   data() {
      return {
         locales: {
            en: 'en',
            pl: 'pl',
            uwu: 'uwu'
         }
      }
   },

   methods: {
      change(event) {
         this.$emit('update:locale', event.target.value)
      }
   }
}
</script>
