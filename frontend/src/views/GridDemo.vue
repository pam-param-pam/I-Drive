<template>
  <div class="wrapper">
    <div class="toolbar">
      <label>
        Grid items per row
        <input
          v-model.number="gridItems"
          type="number"
          min="2"
          max="20"
        >
      </label>
      <input
        v-model.number="gridItems"
        type="range"
        min="2"
        max="20"
      >
      <span>
        <button @mousedown="$refs.scroller.scrollToItem(scrollTo)">Scroll To: </button>
        <input
          v-model.number="scrollTo"
          type="number"
          min="0"
          :max="list.length - 1"
        >
      </span>
    </div>
    <div class="grid">
      <RecycleScroller
        ref="scroller"
        id="scroller"
        class="scroller"
        :items="list"
        :item-size="tileHeight"
        :grid-items="gridItems"
        :item-secondary-size="tileWidth"
        v-slot="{ item, index }"
      >
        <div class="item-wrapper">
          <div
            ref="wrapper"
            class="item"
            role="button"
          >
            <div>
              <img
                :style="`width: ${imageWidth}px; height: ${imageHeight}px`"

                :key="item.id"
                :src="item.thumbnail_url"
              />
            </div>
            <div class="size">
              <p >{{ item.size }}</p>
            </div>
            <div class="name">
              <p >{{ item.name }}</p>
            </div>
          </div>
        </div>

      </RecycleScroller>
    </div>

  </div>


</template>

<script>
import { RecycleScroller } from "vue-virtual-scroller"


export default {
   components: {
      RecycleScroller,
   },
   data() {
      return {
         list: [],
         gridItems: 6,
         scrollTo: 500,
         tileWidth: 0,
         tileHeight: 0,
         imageHeight: 0,
         imageWidth: 0,
      }
   },

   async created() {
      let response = await fetch('http://localhost:5173/data.json');

      let jsonData = await response.json()
      this.list = jsonData.folder.children

   },
   mounted() {
      let element = document.getElementById("scroller")
      this.calculateGridLayout(element.clientWidth-15)

      window.addEventListener("resize", this.calculateGridLayoutWrapper);
   },
   unmounted() {

      window.addEventListener("resize", this.calculateGridLayoutWrapper);

   },
   methods: {
      calculateGridLayoutWrapper() {
         let element = document.getElementById("scroller");
         this.calculateGridLayout(element.clientWidth);
      },
      calculateGridLayout(containerWidth) {


         const maxTileWidth = 400;

         // Calculate the maximum number of tiles that can fit using the minimum width
         let numberOfTiles = Math.ceil(containerWidth / maxTileWidth);

         // Calculate the actual width of each tile
         let tileWidth = containerWidth / numberOfTiles;

         // Update the data properties
         this.gridItems = numberOfTiles;
         this.tileWidth = tileWidth;
         this.tileHeight = this.tileWidth*300/400

         this.imageWidth = 175/400 * this.tileWidth
         this.imageHeight = 240/300 * this.tileHeight - 45/numberOfTiles



      },
   }
}
</script>



<style scoped>


.grid {
 flex: 1; /* Fills available space in the flex container */
 overflow-y: hidden; /* Allows vertical scrolling if content overflows */

}

.grid .scroller {
 padding-bottom:  1em;
 background-color: #f2f2f2;
 height: calc(100% - 20px);
 overflow-y: auto;

}
.wrapper {
 display: flex;
 flex-direction: column;
 overflow: hidden;
 height: 100%;

}


.grid .item-wrapper:hover {
 background: #f36363;
 opacity: 0.5;

}

.grid .item-wrapper {
 border-radius: 10px;
 margin: 0.5em;
 background-color: #ffffff;
 overflow: hidden;
 box-shadow: rgba(0, 0, 0, 0.06) 0 1px 3px, rgba(0, 0, 0, 0.12) 0 1px 2px;

}

.grid .item-wrapper .item {
 display: flex;
 flex-direction: column;
 text-align: center;
}

.grid .item-wrapper .item img {
 /*-webkit-filter: blur(35px);*/
 margin-top: 0.5em;
 box-shadow: rgba(0, 0, 0, 0.06) 0 1px 3px, rgba(0, 0, 0, 0.12) 0 1px 2px;

 object-fit: cover;
 background: #ffffff;

}
.grid .item-wrapper .item .name p {
 text-overflow: ellipsis;
 overflow: hidden;
 font-size: 15px;
 margin: 0.5em;

}

.grid .item-wrapper .item .size  {
 display: none;
}

</style>
