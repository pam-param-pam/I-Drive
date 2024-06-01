<template>
  <div>
    <ul class="search-list">
      <li
        v-for="item in items"
        tabindex="0"
        @click="click(item)"
        :aria-label="item.name"
        :key="item.id"
        :class="{'folder': item.type === 'folder', 'file': item.type !== 'folder'}"
      >
        {{ item.name }}
      </li>
    </ul>
  </div>
</template>

<script>

import {search} from "@/api/search.js"

export default {
  name: "file-list",
  props: ["items"],
  computed: {
    async filteredOptions() {
      let res
      res = await search(this.query)
      console.log(res)

      res = [{'id': 1, 'name': 'filename1.txt', 'type': 'text'}, {'id': 2, 'name': 'filename2.pdf', 'type': 'pdf'}, {'id': 3, 'name': 'filename3.jpg', 'type': 'image'}, {'id': 4, 'name': 'foldername1', 'type': 'folder'}, {'id': 5, 'name': 'foldername2', 'type': 'folder'}, {'id': 6, 'name': 'foldername3', 'type': 'folder'}]

      return res
      // const regOption = new RegExp(this.searchFilter, 'ig')
      // for (const option of this.options) {
      //   if (this.searchFilter.length < 1 || option.name.match(regOption)){
      //     if (filtered.length < this.maxItem) filtered.push(option)
      //   }
      // }
      //return filtered
    },
  },

  methods: {
    click(item) {
      console.log("CLIIICK")


    }
  }
}
</script>

<style lang="scss" scoped>
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
</style>
