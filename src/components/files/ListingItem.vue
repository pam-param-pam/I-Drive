<template>
  <div
    class="item"
    role="button"
    tabindex="0"
    :draggable="isDraggable"
    @dragstart="dragStart"
    @dragover="dragOver"
    @drop="drop"
    @dblclick="open"
    @click="click"
    :data-dir="item.isDir"
    :data-type="type"
    :aria-label="item.name"

    :aria-selected="isSelected"
  >
    <div>
      <img
        v-if="item.preview_url && type === 'image'"
        :src="item.preview_url"
      />
      <img
        v-else-if="item.download_url && type === 'image'"
        :src="item.download_url"
      />
      <img
        v-else-if="item.thumbnail_url && type === 'video'"
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
import moment from "moment"
import {move} from "@/api/item.js"


export default {

  name: "item",
  data: function () {
    return {
      touches: 0,
    }
  },
  props: [
    "readOnly",
    "item",
    "mode",
  ],
  computed: {
    ...mapState(["user", "perms", "selected", "settings", "items"]),
    ...mapGetters(["selectedCount", "getFolderPassword"]),
    type() {
      if (this.item.isDir) return "folder"
      if (this.item.type === "application") return "pdf"
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

    humanSize: function () {
      return this.type === "invalid_link" ? "invalid link" : filesize(this.item.size)
    },
    humanTime: function () {

      if (this.settings?.dateFormat) {
        return moment(this.item.created).format("L LT")
      }
      return moment(this.item.created).fromNow()
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
      try {
        await move({ids: listOfIds, "new_parent_id": this.item.id})

        //let updatedItem = this.items.filter(item => !listOfIds.includes(item.id))
        //this.$store.commit("setItems", updatedItem)
        //todo
        let message = `Moved to ${this.item.name}!`
        this.$toast.success(message)

      } catch (error) {
        console.log(error)
        //nothing has to be done
      }

    },


    click: function (event) {

      if (!event.shiftKey && this.selected.length > 0) {
        if (! this.isSelected) {
          this.resetSelected()
        }
      }

      if (this.isSelected && this.selected.length > 0)  {
        this.removeSelected(this.item)
        return
      }

      this.addSelected(this.item)


      /*
      let lastIndex = -1
      let currentIndex = -1
      for (let i = 0; i < this.items.length; i++) {
        if (this.items[i].id === this.selected[this.selected.length - 1]?.id) {
          lastIndex = i
        }
        if (this.items[i].id === this.item.id) {
          currentIndex = i
        }
      }
      console.log("lastIndex: " + lastIndex)
      console.log("currentIndex: " + currentIndex)
       */

    },
    open: function () {
      if (this.mode === "share") {
        this.$emit('onOpen', this.item)
        return
      }
      if (this.mode === "trash") {
        this.resetSelected()
        this.addSelected(this.item)
        this.$store.commit("showHover", "restoreFromTrash")
        return
      }

      if (this.item.isDir) {
        if (this.item.isLocked === true) {
          let password = this.getFolderPassword(this.item.id)
          if (!password) {
            this.$store.commit("showHover", {
              prompt: "FolderPassword",
              props: {folderId: this.item.id},
              confirm: () => {
                this.$router.push({name: "Files", params: {"folderId": this.item.id}})
              },
            })
            return
          }
        }
        this.$router.push({name: "Files", params: {"folderId": this.item.id}})

      } else {

        if (this.item.type === "audio" || this.item.type === "video" || this.item.type === "image" ||  this.item.size >= 25 * 1024 * 1024 || this.item.extension === ".pdf") {
          this.$router.push({name: "Preview", params: {"fileId": this.item.id}} )

        }
        else {
          this.$router.push({name: "Editor", params: {"fileId": this.item.id}} )

        }

      }
    },
  },
}
</script>
