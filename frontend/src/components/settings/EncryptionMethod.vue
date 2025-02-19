<template>
   <select :value="encryptionMethod" v-on:change="change">
      <option v-for="(method, value) in encryptionMethods" :key="value" :value="value">
         {{ $t(method) }}
      </option>
   </select>
</template>

<script>
import { encryptionMethods } from '@/utils/constants.js'

export default {
   name: 'encryptionMethod',

   computed: {
      encryptionMethods() {
         return encryptionMethods
      }
   },

   props: ['encryptionMethod'],

   emits: ['update:encryptionMethod'],

   methods: {
      change(event) {
         this.$emit('update:encryptionMethod', parseInt(event.target.value))
      }
   }
}
</script>
