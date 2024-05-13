<template>
  <div id="search">
    <div id="input">
      <input

        type="text"
        v-model="query"
        ref="input"
        :aria-label="$t('search.search')"
        :placeholder="$t('search.search')"
      />
    </div>
  </div>
</template>

<script>
import FileList from "@/components/prompts/FileList.vue";
import {search} from "@/api/search.js";
import {mapGetters, mapMutations} from "vuex";

export default {
  name: "search",
  components: {FileList},
  emits: ['search-items', 'exit'],

  data: function () {
    return {
      selected: {},
      query: '',
    }
  },

  computed: {
    ...mapGetters(["getFolderPassword"])
  },


  methods: {
    ...mapMutations(["setIsTrash"]),
    async search() {
      if (this.query === '') return []
      const regex = /(\w+):(\S+)\s*/g;
      let match;
      let argumentDict = {};
      let lastIndex = 0;

      while ((match = regex.exec(this.query)) !== null) {
        // Extracting argument name and value
        const [, name, value] = match;
        argumentDict[name] = value;
        lastIndex = regex.lastIndex;

      }
      // Extracting remaining string
      argumentDict["query"] = this.query.substring(lastIndex).trim();


      let searchItems = await search(argumentDict)
      this.$emit('search-items', searchItems);

    },

    async exit() {
      this.query = '';


    },

  },
  watch: {
    query() {
      if (this.query === '') {
        this.$store.commit("setOpenSearchState", false);
        this.$emit('exit');

      }
      else {
        this.$store.commit("setOpenSearchState", true);
        this.search()

      }

    }
  }
};
</script>
