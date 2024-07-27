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
import {mapGetters, mapState} from "vuex"

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
    ...mapState(["searchFilters", "disabledCreation"]),
    ...mapGetters(["getFolderPassword"])
  },


  methods: {
    async search() {


      //copying to not mutate vuex store state
      let searchDict = { ...this.searchFilters }
      searchDict["query"] = this.query
      this.$emit('onSearchQuery', searchDict)

    },
    onTuneClick() {
      this.$store.commit("showHover", {
        prompt: "SearchTunePrompt",
        confirm: () => {
          this.search()

        },
      })

    },
    async exit() {
      this.$store.commit("setDisabledCreation", false)
      this.$store.commit("resetSelected")
      this.$emit('exit')
      this.query = ''
    },

  },
  watch: {
    query() {
      if (this.query === '') {
        this.exit()

      }
      else {
        this.$store.commit("setDisabledCreation", true)
        this.$store.commit("resetSelected")
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
 /* Add other styles as needed */
}

.material-icons:hover {
 color: #007BFF; /* Change to the desired hover color */
 transform: scale(1.1); /* Slightly enlarge the icon on hover */
}
</style>