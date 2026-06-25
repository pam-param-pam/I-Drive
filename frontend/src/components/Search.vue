<template>
   <div id="search" @keydown="keyEvent">
      <div id="input">
         <input
           :disabled="disabled"
           :class="{ disabled }"
           ref="input"
           v-model="query"
           :aria-label="$t('search.search')"
           :placeholder="$t('search.search')"
           :title="$t('search.search')"
           autocomplete="off"
           type="text"
         />

         <i
           v-if="searchActive"
           :aria-label="$t('search.close')"
           :title="$t('search.close')"
           class="material-icons"
           @click="exit"
         >close</i>

         <i
           v-if="advanced"
           :aria-label="$t('search.tuneSearch')"
           :title="$t('search.tuneSearch')"
           class="material-icons"
           :class="{ disabled }"
           @click="onTuneClick"
         >tune</i>
      </div>
   </div>
</template>

<script>
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"
import throttle from "lodash.throttle"

export default {
   name: "search",
   props: {
      advanced: Boolean,
      disabled: Boolean
   },
   emits: ["onSearchQuery"],

   data() {
      return {
         selected: {},
         query: "",
      }
   },

   computed: {
      ...mapState(useMainStore, ["searchFilters", "searchActive", "currentPrompt"])
   },

   methods: {
      ...mapActions(useMainStore, ["showHover", "resetSelected", "setSearchActive", "setItemsError", "setSearchItems", "setLastFile", "setLastFolder"]),

      search: throttle(async function(override) {
         if (!this.query && !override) return
         this.setLastFile(null)
         this.setLastFolder(null)
         
         //copying to not mutate vuex store state
         let searchDict = { ...this.searchFilters.external }
         searchDict["query"] = this.query
         this.$emit("onSearchQuery", searchDict)
      }, 500),

      keyEvent(event) {
         // Ctrl is pressed
         if ((event.ctrlKey || event.metaKey)) {
            let key = event.key.toLowerCase()
            //allow user to select all text in search and make it not select all items at the same time
            if (key === "a") {
               if (document.activeElement === this.$refs.input) {
                  event.stopImmediatePropagation()
               }
            }
         }
         //allow to exit search with ESC
         if (event.code === "Escape" && this.searchActive && !this.currentPrompt) {
            this.exit()
         }
      },
      onTuneClick() {
         if (this.disabled) return
         this.showHover({
            prompt: "SearchTunePrompt",
            confirm: () => {
               this.search(true)
            }
         })
      },

      async exit() {
         this.resetSelected()
         this.query = ""
         this.setSearchItems(null)
         this.setSearchActive(false)
         this.setItemsError(null)
      }
   },

   watch: {
      query() {
         if (this.query === "") {
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
   padding-right: 1.5em;
}

.material-icons.disabled {
   cursor: not-allowed;
   opacity: 0.4;
   pointer-events: stroke;
   transform: none;
}

.material-icons.disabled:hover {
   color: inherit;
   transform: none;
}

#search input:disabled {
   cursor: not-allowed;
}
</style>
