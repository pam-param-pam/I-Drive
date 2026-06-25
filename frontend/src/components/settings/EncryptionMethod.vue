<template>
   <select :value="modelValue" v-on:change="change">
      <option v-for="option in normalizedOptions" :key="option.value" :value="option.value">
         {{ translate ? $t(option.label) : option.label }}
      </option>
   </select>
</template>

<script>
export default {
   name: "BaseSelect",

   props: {
      modelValue: {
         required: true
      },
      options: {
         type: [Array, Object],
         required: true
      },
      translate: {
         type: Boolean,
         default: true
      },
      valueType: {
         type: String,
         default: "string"
      }
   },

   emits: ["update:modelValue"],

   computed: {
      normalizedOptions() {
         if (Array.isArray(this.options)) {
            return this.options
         }

         return Object.entries(this.options).map(([value, label]) => ({ value, label }))
      }
   },

   methods: {
      change(event) {
         let value = event.target.value

         if (this.valueType === "number") {
            value = Number(value)
         }

         this.$emit("update:modelValue", value)
      }
   }
}
</script>