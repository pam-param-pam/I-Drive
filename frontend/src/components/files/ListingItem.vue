<template>
  <div class="item-wrapper">
    <div
      ref="wrapper"
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

      <div :style="divStyle"
      >
        <img
          v-if="item.preview_url && type === 'image' && item.size > 0"
          v-lazy="{src: item.preview_url, error: '/img/imageFailed.png'}"
        />
        <img
          v-else-if="item.download_url && type === 'image' && item.size > 0"
          v-lazy="{src: item.download_url, error: '/img/imageFailed.png'}"
          :style="`min-width: ${imageWidth}px; height: ${imageHeight}px;`"

        />
        <img
          v-else-if="item.thumbnail_url && type === 'video'"
          v-lazy="{src: item.thumbnail_url, error: '/img/imageFailed.png'}"
          :style="imageStyle"


        />
        <i v-else class="material-icons" :style="iconStyle"></i>
      </div>
      <div class="size">
        <p >{{ item.size }}</p>
      </div>
      <div class="name">
        <p >{{ item.name }}</p>
      </div>
    </div>
  </div>

</template>

<script>
import {filesize} from "@/utils"
import moment from "moment/min/moment-with-locales.js"
import {move} from "@/api/item.js"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"

export default {

   name: "item",

   emits: ['onOpen'],
   props: ["readOnly", "item", "imageWidth", "imageHeight"],

   computed: {
      ...mapState(useMainStore, ["perms", "selected", "settings", "items", "selectedCount"]),
      type() {
        console.log(this.item.extension)
         if (this.item.isDir) return "folder"
         if (this.item.type === "application") return "pdf"
         if (this.item.extension === ".epub") return "ebook"
         return this.item.type
      },
      isSelected() {
         return this.selected.some(obj => obj.id === this.item.id)
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
            if (item.id === this.item.id) {
               return false
            }
         }
         return true
      },
      iconSize() {
         return this.imageWidth / 12
      },
      iconStyle() {
         if(this.settings.viewMode === "grid") {
            return `font-size: ${this.iconSize}em;`
         }
         return null
      },
      imageStyle() {
         if(this.settings.viewMode === "grid") {
            return `min-width: ${this.imageWidth}px; height: ${this.imageHeight}px;`
         }
         return null

      },
      divStyle() {
         if(this.settings.viewMode === "grid") {
            return `min-width: ${this.imageWidth}px; height: ${this.imageHeight}px;`
         }
         return null
      },

   },

   methods: {
      ...mapActions(useMainStore, ["addSelected", "removeSelected", "resetSelected"]),
      myScroll() {
         let wrapper = this.$refs.wrapper
         wrapper.scrollIntoView()
         this.addSelected(this.item)
      },

      humanSize() {
         return filesize(this.item.size)
      },
      humanTime() {

         if (this.settings.dateFormat) {
            return moment(this.item.created, "YYYY-MM-DD HH:mm").format("DD/MM/YYYY, hh:mm")
         }
         //todo czm globalny local nie dzIała?
         let locale = this.settings?.locale || "en"

         moment.locale(locale)
         // Parse the target date
         return moment(this.item.created, "YYYY-MM-DD HH:mm").endOf('second').fromNow()
      },

      dragStart() {
         if (this.selectedCount === 0) {
            this.addSelected(this.item)
            return
         }

         if (!this.isSelected) {
            this.resetSelected()
            this.addSelected(this.item)
         }
      },

      dragOver(event) {
         if (!this.canDrop) return

         let el = event.target
         for (let i = 0; i < 5; i++) {
            if (!el.classList.contains("item")) {
               el = el.parentElement
            }
         }
         el.style.opacity = 1
      },

      async drop(event) {
         if (!this.canDrop) return
         if (this.selectedCount === 0) return

         let listOfIds = this.selected.map(obj => obj.id)
         await move({ids: listOfIds, "new_parent_id": this.item.id})

         let message = this.$t('toasts.movedItems')
         this.$toast.success(message)

        this.resetSelected()
      },
      open() {
         this.$emit('onOpen', this.item)
      },
      click(event) {
         // Deselect items if no shift or ctrl key is pressed and there are selected items
         // then add current item to selected if it wasn't previously selected
         if (!event.ctrlKey && !event.shiftKey && this.selected.length > 0) {
            let shouldAdd = (!this.isSelected || this.selected.length >= this.items.length) && this.items.length > 1
            this.resetSelected()
            if (shouldAdd) {
               this.addSelected(this.item)
            }
            return
         }

         // Shift+Click functionality for range selection
         if (event.shiftKey && this.selectedCount > 0) {

            let fromItem = this.item
            let toItem = this.selected[this.selected.length - 1]

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
         } else {
            this.addSelected(this.item)
         }

      },

   },
}
</script>
<style scoped>
.grid .item-wrapper:hover {
 box-shadow: 0 1px 3px rgba(0, 0, 0, .12), 0 1px 2px rgba(0, 0, 0, .24) !important;
 background: var(--light-blue);
 transform: scale(1.03);

}


.grid .item-wrapper {
 border-radius: 10px;
 margin: 0.5em;
 background-color: #f0f1fd;
 overflow: hidden;
 box-shadow: rgba(0, 0, 0, 0.06) 0 1px 3px, rgba(0, 0, 0, 0.12) 0 1px 2px;

}

.grid .item-wrapper .item {
 display: flex;
 flex-direction: column;
 text-align: center;
 transition: .1s ease background, .1s ease opacity;
 cursor: pointer;
 user-select: none;
}
.grid .item-wrapper .item i {


}
.grid .item-wrapper .item img {
 /*-webkit-filter: blur(35px);*/
 margin-top: 0.5em;
 max-width: 100%;
 object-fit: cover;
 background: #ffffff;

}
.grid .item-wrapper .item .name p {
 text-overflow: ellipsis;
 overflow: hidden;
 font-size: 15px;
 margin: 1.5em 2em 0.5em;
 white-space: nowrap;
}

.grid .item-wrapper .item .size  {
 display: none;
}

.grid .item-wrapper [aria-selected=true] {
 background: #c4e6ff !important;
}

.grid .item-wrapper [data-dir=true] p {
 font-size: 20px !important;
 margin-top: 0.5em !important;
 padding-bottom: 0.25em !important;
}




.list .item-wrapper {
 flex-direction: column;
 width: 100%;
 max-width: 100%;
 margin: 0;
}

.list .item-wrapper .item {
 width: 100%;
 margin: 0;
 border: 1px solid rgba(0, 0, 0, 0.1);
 padding: 1em;
 border-top: 0;
}
.list .item-wrapper .item i {
  font-size: 1em;

}
.list h2 {
 display: none;
}

/*#listing .item[aria-selected=true] {*/
/*  background: var(--blue) !important;*/
/*  !*color: var(--item-selected) !important;*!*/
/*}*/

.list .item div:first-of-type {
 width: 3em;
}

.list .item div:first-of-type i {
 font-size: 2em;
}

.list .item div:first-of-type img {
 width: 2em;
 height: 2em;
}

.list .item div:last-of-type {
 width: calc(100% - 3em);
 display: flex;
 align-items: center;
}

.list .item-wrapper .item .name {
 width: 50%;
}

.list .item-wrapper .item .size {
 width: 25%;
}

/*#listing .item.header {*/
/* display: none !important;*/
/* background-color: #ccc;*/
/*}*/

.list .header i {
 font-size: 1.5em;
 vertical-align: middle;
 margin-left: .2em;
}

.list .item.header {
 display: flex !important;
 background: #fafafa;
 z-index: 999;
 padding: .85em;
 border: 0;
 border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.list .item.header>div:first-child {
 width: 0;
}

.list .item.header .name {
 margin-right: 3em;
}

.list .header a {
 color: inherit;
}

.list .item.header>div:first-child {
 width: 0;
}

.list .name {
 font-weight: normal;
}

.list .item.header .name {
 margin-right: 3em;
}

.list .header span {
 vertical-align: middle;
}

.list .header i {
 opacity: 0;
 transition: .1s ease all;
}

.list .header p:hover i,
.list .header .active i {
 opacity: 1;
}

.list .item.header .active {
 font-weight: bold;
}
</style>