<template>
  <div id="search" class="dropdown">
    <div id="input">
      <input

        type="text"
        @focusout="exit()"
        @focus="showOptions()"
        v-model="searchFilter"
        ref="input"
        :aria-label="$t('search.search')"
        :placeholder="$t('search.search')"
      />

    </div>
    <div class="search-list dropdown-content"
         v-show="optionsShown">
      <div>
        <ul >
          <li
            v-for="item in searchItems"
            @click="selectOption(item)"
            tabindex="0"
            :aria-label="item.name"
            :key="item.id"
            :class="{'folder': item.isDir === true, 'file': item.isDir !== true}"
          >
            {{ item.name }}
          </li>
        </ul>
      </div>
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

  data: function () {
    return {
      selected: {},
      optionsShown: false,
      searchFilter: '',
      searchItems: []
    }
  },
  created() {
    this.$emit('selected', this.selected);
  },

  computed: {
    ...mapGetters(["getFolderPassword"])
  },
  methods: {

    async search() {
      if (this.searchFilter === '') return []
      this.searchItems = await search(this.searchFilter)

    },
    selectOption(item) {

      console.log(item)
      if (item.isDir) {
        if (item.isLocked === true) {
          let password = this.getFolderPassword(item.id)
          if (!password) {
            this.$store.commit("showHover", {
              prompt: "FolderPassword",
              props: {folderId: item.id},
              confirm: () => {
                this.$router.push({name: `Listing`, params: {"folderId": item.id}});
              },
            });
            return
          }
        }
        this.$router.push({name: `Listing`, params: {"folderId": item.id}});

      } else {
        //
        if (item.type === "audio" || item.type === "video" || item.type === "image" || item.size >= 25 * 1024 * 1024 || item.extension === ".pdf") {
          this.$router.push({path: `/preview/${item.id}`});

        }
        else {
          this.$router.push({path: `/editor/${item.id}`});

        }

      }
    },
    showOptions(){
      if (!this.disabled) {
        this.searchFilter = '';
        this.optionsShown = true;
      }
    },
    async exit() {

      if (!this.selected.id) {

        this.selected = {};
        this.searchFilter = '';
      } else {
        this.searchFilter = this.selected.name;
      }
      this.$emit('selected', this.selected);
      this.optionsShown = false;
    },


  },
  watch: {
    searchFilter() {
      if (this.searchFilter === '') {
        this.$store.commit("changeOpenSearchState", false);

      }
      else {
        this.$store.commit("changeOpenSearchState", true);

      }
      this.search()

    }
  }
};
</script>


<style lang="scss" scoped>
.dropdown {
  position: relative;
  display: block;
  margin: auto;

  .dropdown-content {
    position: relative;
    left: 60px;
    top: 10px;
    opacity: 1;
    background-color: #ffffff; /* Change the background color */
    max-width: 400px;
    border: 1px solid #e7ecf5;
    border-radius: 10px; /* Round the edges */
    box-shadow: 0px 10px 40px 0 rgba(0,0,0,0.1), 0px 20px 50px -10px rgba(0,0,0,0.2); /* Adjust the box-shadow */
    overflow: auto;
    z-index: 1;

    .dropdown-item {
      color: black;
      line-height: 3em;
      padding: 8px;
      text-decoration: none;
      display: block;
      cursor: pointer;
      &:hover {
        background-color: #e7ecf5;
      }
    }
  }
  .dropdown:hover .dropdown-content {
    display: block;
  }
.search-list {
  max-height: 50vh;
  overflow: auto;
  list-style: none;
  margin: 0;
  padding: 0;
  width: 100%;
}

  .search-list li {
    width: 100%;
    user-select: none;
    border-radius: .2em;
    padding: .3em;
  }

  .search-list li[aria-selected=true] {
    background: var(--blue) !important;
    color: #fff !important;
    transition: .1s ease all;
  }

  .search-list li:hover {
    background-color: #e9eaeb;
    cursor: pointer;
  }

  .search-list li:before {
    color: #6f6f6f;
    vertical-align: middle;
    line-height: 1.4;
    font-family: 'Material Icons';
    font-size: 1.75em;
    margin-right: .25em;
  }

  .search-list li.folder:before {
    content: "folder";
  }
  .search-list li.file:before {
    content: "description";
  }
}
</style>