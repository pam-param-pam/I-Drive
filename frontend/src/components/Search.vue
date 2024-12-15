<template>
  <div id="search">
    <div id="input">
      <input
        type="text"
        autocomplete="off"

        v-model="query"
        ref="input"
        :aria-label="$t('search.search')"
        :title="$t('search.search')"
        :placeholder="$t('search.search')"
      />
      <i v-if="disabledCreation" class="material-icons"
         @click="exit"
         :aria-label="$t('search.close')"
         :title="$t('search.close')"
      >close</i>
      <i class="material-icons"
         @click="onTuneClick"
         :aria-label="$t('search.tuneSearch')"
         :title="$t('search.tuneSearch')"
      >tune</i>
    </div>
  </div>
</template>


<script>

import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"
import throttle from "lodash.throttle"

export default {
   name: "search",
   emits: ['onSearchQuery', 'exit'],

   data() {
      return {
         selected: {},
         query: '',
      }
   },

   computed: {
      ...mapState(useMainStore, ["searchFilters", "disabledCreation"]),
   },
    //TODO FIX THIS SHIT

   methods: {
      ...mapActions(useMainStore, ["showHover", "setDisabledCreation", "resetSelected"]),
      search: throttle(async function (event) {
         //copying to not mutate vuex store state
         let searchDict = {...this.searchFilters}
         searchDict["query"] = this.query
         this.$emit('onSearchQuery', searchDict)

      }, 500),
      onTuneClick() {
         this.showHover({
            prompt: "SearchTunePrompt",
            confirm: () => {
               this.search()
            },
         })
      },

      async exit() {
         this.setDisabledCreation(false)
         this.resetSelected()
         this.$emit('exit')
         this.query = ''
      },

   },
   watch: {
      query() {
         if (this.query === '') {
            this.exit()
         } else {
            this.setDisabledCreation(true)
            this.resetSelected()
            this.search()
         }
      }
   }
}
</script>
<style scoped>

.material-icons {
 cursor: pointer;
 transition: color 0.3s, transform 0.3s;
}

.material-icons:hover {
 color: #007BFF;
 transform: scale(1.1);
}
</style>