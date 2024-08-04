<template>
  <div
    ref="wrapper"
    class="item"
    role="button"
    tabindex="0"
    :draggable="isDraggable"
    @dragstart="dragStart"
    @dragover="dragOver"
    @drop="drop"
    @dblclick="$emit('onOpen', item)"
    @click="click"
    :data-dir="item.isDir"
    :data-type="type"
    :aria-label="item.name"

    :aria-selected="isSelected"
  >
    <div>
      <img
        v-if="item.preview_url && type === 'image' && item.size > 0"
        v-lazy="item.preview_url"
        :src="item.preview_url"
      />
      <img
        v-else-if="item.download_url && type === 'image' && item.size > 0"
        v-lazy="item.download_url"
        :src="item.download_url"
      />
      <img
        v-else-if="item.thumbnail_url && type === 'video'"
        v-lazy="item.thumbnail_url"
        :src="item.thumbnail_url"
      />
      <i v-else class="material-icons"></i>
    </div>
    <div>
      <p class="name">{{ item.name }}</p>


      <p v-if="item.isDir" class="size" data-order="-1">&mdash;</p>
      <p v-else class="size" :data-order="item.size">{{ humanSize() }}</p>


      <p class="created">
        <time :datetime="item.created">{{ humanTime() }}</time>
      </p>

    </div>
  </div>
</template>

<script>
import {mapMutations, mapGetters, mapState} from "vuex"
import {filesize} from "@/utils"
import moment from "moment/min/moment-with-locales.js"
import {move} from "@/api/item.js"


export default {

  name: "item",

  emits: ['onOpen'],

  props: [
    "readOnly",
    "item",
  ],
  computed: {
    ...mapState(["user", "perms", "selected", "settings", "items"]),
    ...mapGetters(["selectedCount", "getFolderPassword"]),
    type() {
      if (this.item.isDir) return "folder"
      if (this.item.type === "application") return "pdf"
      if (this.item.extension === ".epub" || this.item.extension === ".mobi") return "ebook"
      return this.item.type
    },
    isSelected() {
      return this.selected.includes(this.item)
    },
    isDraggable() {
      return this.readOnly === false && this.perms?.modify
    },
    canDrop() {
      if (!this.item.isDir || this.readOnly !== false) return false

      for (let item of this.selected) {
        if (item === this.item) {
          return false
        }
      }
      return true
    },

  },

  methods: {
    ...mapMutations(["addSelected", "removeSelected", "resetSelected"]),
    myScroll() {
      let wrapper = this.$refs.wrapper
      wrapper.scrollIntoView()
      this.addSelected(this.item)
    },
    humanSize: function () {
      return this.type === "invalid_link" ? "invalid link" : filesize(this.item.size)
    },
    humanTime: function () {

      if (this.settings.dateFormat) {
        return moment(this.item.created, "YYYY-MM-DD HH:mm").format("DD/MM/YYYY, hh:mm")
      }
      //todo czm globalny local nie dzIała?
      let locale = this.settings?.locale || "en"

      moment.locale(locale)
      // Parse the target date
      return moment(this.item.created, "YYYY-MM-DD HH:mm").endOf('second').fromNow()
    },

    dragStart: function () {

      if (this.selectedCount === 0) {
        this.addSelected(this.item)
        return
      }

      if (!this.isSelected) {
        this.resetSelected()
        this.addSelected(this.item)
      }


    },

    dragOver: function (event) {
      if (!this.canDrop) return

      //event.preventDefault()
      let el = event.target
      for (let i = 0; i < 5; i++) {
        if (!el.classList.contains("item")) {
          el = el.parentElement
        }
      }

      el.style.opacity = 1

    },
    drop: async function (event) {

      if (!this.canDrop) return
      //event.preventDefault()

      if (this.selectedCount === 0) return

      let listOfIds = this.selected.map(obj => obj.id)

      await move({ids: listOfIds, "new_parent_id": this.item.id})

      let message = this.$t('toasts.movedItems')
      this.$toast.success(message)



    },

    click: function (event) {

      // Deselect items if no shift or ctrl key is pressed and there are selected items
      // then add current item to selected if it wasn't previously selected
      if (!event.ctrlKey && !event.shiftKey && this.selected.length > 0) {
        let shouldAdd = !this.isSelected || this.selected.length >= this.items.length
        this.resetSelected()
        if (shouldAdd) {
          this.addSelected(this.item)
        }
        return
      }

      // Shift+Click functionality for range selection
      if (event.shiftKey && this.selectedCount > 0) {

        let fromItem = this.item
        let toItem = this.selected[this.selected.length-1]

        let fromIndex = fromItem.index
        let toIndex = toItem.index

        let start = Math.min(fromIndex, toIndex)
        let end = Math.max(fromIndex, toIndex)
        this.resetSelected()

        this.items.forEach(item => {
          if (item.index >= start && item.index <= end) {
            this.addSelected(item)
          }
        })
        return

      }
      // Remove the selected item if it is already selected and there are selected items
      if (this.isSelected) {
        this.removeSelected(this.item)
      }
      else {
        this.addSelected(this.item)
      }

    },

  },
}
</script>
