<template>
   <div id='search'>
      <div id='input'>
         <input
            ref='input'
            v-model='query'
            :aria-label="$t('search.search')"
            :placeholder="$t('search.search')"
            :title="$t('search.search')"
            autocomplete='off'
            type='text'
         />
         <i
            v-if='searchActive'
            :aria-label="$t('search.close')"
            :title="$t('search.close')"
            class='material-icons'
            @click='exit'
         >close</i
         >
         <i
            :aria-label="$t('search.tuneSearch')"
            :title="$t('search.tuneSearch')"
            class='material-icons'
            @click='onTuneClick'
         >tune</i
         >
      </div>
   </div>
</template>

<script>
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import throttle from 'lodash.throttle'

export default {
   name: 'search',

   emits: ['onSearchQuery', 'exit'],

   data() {
      return {
         selected: {},
         query: '',
         exited: false
      }
   },

   computed: {
      ...mapState(useMainStore, ['searchFilters', 'searchActive'])
   },
   async mounted() {
      this.exited = true
      this.query = this.searchFilters.query
      await this.$nextTick() //this is vevy important
      this.exited = false
   },
   created() {
      window.addEventListener('keydown', (event) => {
         // Ctrl is pressed
         if ((event.ctrlKey || event.metaKey)) {
            let key = event.key.toLowerCase()
            //allow user to select all text in search and make it not select all items at the same time
            if (key === 'a') {
               if (document.activeElement === this.$refs.input) {
                  event.stopImmediatePropagation()
               }
            }
         }
         //allow to exit search with ESC
         if (event.code === 'Escape' && this.searchActive) {
            this.exit()
         }
      })
   },
   methods: {
      ...mapActions(useMainStore, ['setLastItem', 'showHover', 'resetSelected', 'setSearchFilters']),

      search: throttle(async function(override) {
         if (!this.query && !override) return
         this.setLastItem(null)
         //copying to not mutate vuex store state
         let searchDict = { ...this.searchFilters }
         searchDict['query'] = this.query
         this.setSearchFilters(searchDict)
         this.$emit('onSearchQuery', searchDict)
      }, 500),

      onTuneClick() {
         this.showHover({
            prompt: 'SearchTunePrompt',
            confirm: () => {
               this.search(true)
            }
         })
      },

      async exit() {
         console.log('exiting search')
         this.resetSelected()
         this.$emit('exit')

         this.exited = true
         this.query = ''
         this.exited = false
         let searchDict = { ...this.searchFilters }
         searchDict['query'] = ''
         this.setSearchFilters(searchDict)
      }
   },

   watch: {
      "searchFilters.query"() {
         if (!this.searchFilters.query) this.query = ''
      },
      query() {
         if (this.exited) {
            this.exited = false
            return
         }
         if (this.query === '') {
            this.exit()
         } else {
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
 transition: color 0.3s,
 transform 0.3s;
}

.material-icons:hover {
 color: #007bff;
 transform: scale(1.1);
}

#search input {
 color: var(--color-text);
}
</style>
