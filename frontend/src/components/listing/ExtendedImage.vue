<template>
   <div
      ref="container"
      class="image-ex-container"
      @dblclick="zoomAuto"
      @mousedown="mousedownStart"
      @mousemove="mouseMove"
      @mouseup="mouseUp"
      @touchmove="touchMove"
      @touchstart="touchStart"
      @wheel="wheelMove"
   >
      <img
         ref="imgex"
         alt="Failed to load image"
         class="image-ex-img image-ex-img-center"
         @load="onLoad"
         @error="onError"
         :draggable="!turnedOFF"
      />
   </div>
</template>
<script>
import throttle from "lodash.throttle"
import { isMobile } from "@/utils/common.js"
import { getFileRawData } from "@/api/files.js"
import Action from "@/components/header/Action.vue"
import HeaderBar from "@/components/header/HeaderBar.vue"
import { backendInstance } from "@/axios/networker.js"

export default {
   components: { HeaderBar, Action },
   props: {
      src: String,
      thumbSrc: {
         type: String,
         required: false
      },
      imageFullSize: Boolean,
      moveDisabledTime: {
         type: Number,
         default: () => 200
      },
      classList: {
         type: Array,
         default: () => []
      },
      zoomStep: {
         type: Number,
         default: () => 0.25
      }
   },

   data() {
      return {
         scale: 1,
         lastX: null,
         lastY: null,
         inDrag: false,
         touches: 0,
         lastTouchDistance: 0,
         moveDisabled: false,
         disabledTimer: null,
         imageLoaded: false,
         position: {
            center: { x: 0, y: 0 },
            relative: { x: 0, y: 0 }
         },
         maxScale: 4,
         minScale: 0.25,

         turnedOFF: false,
         requestController: null
      }
   },
   computed: {
      imageSrc() {
         if (!this.imageFullSize && this.thumbSrc) return this.thumbSrc
         return this.src
      }
   },
   async mounted() {
      await this.loadImage()

      let container = this.$refs.container
      this.classList.forEach((className) => container.classList.add(className))
      // set width and height if they are zero
      if (getComputedStyle(container).width === "0px") {
         container.style.width = "100%"
      }
      if (getComputedStyle(container).height === "0px") {
         container.style.height = "100%"
      }

      window.addEventListener("resize", this.onResize)
   },

   beforeUnmount() {
      window.removeEventListener("resize", this.onResize)
      document.removeEventListener("mouseup", this.onMouseUp)
   },

   watch: {
      async imageSrc() {
         if (this.requestController) {
            this.requestController.abort()
         }
         this.imageLoaded = false
         this.$refs.imgex.src = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
         await this.loadImage()
         this.setZoom()
         this.setCenter()
      }
   },

   methods: {
      async loadImage() {
         try {
            // Revoke old URL to free memory if any
            if (this._currentBlobUrl) {
               URL.revokeObjectURL(this._currentBlobUrl)
            }

            this.requestController = new AbortController()
            let src = this.imageSrc
            const config = {
               responseType: "arraybuffer",
               signal: this.requestController.signal,
               onDownloadProgress: (event) => {
                  this.updateLoadingToast(event.progress, src)
               }
            }
            let data = await getFileRawData(this.imageSrc, config)

            let blob = data instanceof Blob ? data : new Blob([data])

            this._currentBlobUrl = URL.createObjectURL(blob)
            if (!this.$refs.imgex) return
            this.$refs.imgex.src = this._currentBlobUrl
         } catch (e) {
            if (e.code === "ERR_CANCELED") {
               this.endToast()
               return
            }
            console.error("Error loading image blob:", e)
            this.onError()
         }
      },
      updateLoadingToast(percentage, src) {
         if (src !== this.imageSrc) {
            return
         }
         if (percentage) {
            const translate = this.$t

            percentage = Math.round(percentage * 100)
            this.$toast.update("progress-image", {
               content: translate("toasts.loadingImage", { percentage }),
               options: { timeout: null, type: "info", draggable: false, closeOnClick: false }
            }, true)
            if (percentage >= 100) {
               this.endToast()
            }
         }
      },
      endToast() {
         this.$toast.dismiss("progress-image")
      },
      next(event) {
         event.preventDefault()
      },
      prev(event) {
         event.preventDefault()
      },
      async onError() {
         await backendInstance.get(this.imageSrc)

         this.turnedOFF = true
         this.$refs.imgex.src = "/img/failed.svg"
         if (isMobile()) {
            this.$refs.imgex.style.width = "100%"
         } else {
            this.$refs.imgex.style.width = "40%"
         }
      },
      onLoad() {
         let img = this.$refs.imgex

         this.imageLoaded = true

         if (img === undefined) {
            return
         }

         img.classList.remove("image-ex-img-center")
         this.setCenter()
         img.classList.add("image-ex-img-ready")

         document.addEventListener("mouseup", this.onMouseUp)

         let realSize = img.naturalWidth
         let displaySize = img.offsetWidth

         // Image is in portrait orientation
         if (img.naturalHeight > img.naturalWidth) {
            realSize = img.naturalHeight
            displaySize = img.offsetHeight
         }

         // Scale needed to display the image on full size
         const fullScale = realSize / displaySize

         // Full size plus additional zoom
         this.maxScale = fullScale + 4
      },

      onMouseUp(event) {
         if (this.turnedOFF) return
         this.inDrag = false
      },

      onResize: throttle(function() {
         if (this.imageLoaded) {
            this.setCenter()
            this.doMove(this.position.relative.x, this.position.relative.y)
         }
      }, 100),

      mousedownStart(event) {
         if (this.turnedOFF) return
         this.lastX = null
         this.lastY = null
         this.inDrag = true
         event.preventDefault()
      },

      mouseMove(event) {
         if (this.turnedOFF || !this.inDrag) return
         event.preventDefault()
         this.doMove(event.movementX, event.movementY)
      },

      mouseUp(event) {
         if (this.turnedOFF) return
         this.inDrag = false
         event.preventDefault()
      },

      touchStart(event) {
         if (this.turnedOFF) return
         this.lastX = null
         this.lastY = null
         this.lastTouchDistance = null
         if (event.targetTouches.length < 2) {
            setTimeout(() => {
               this.touches = 0
            }, 300)
            this.touches++
            if (this.touches > 1) {
               this.zoomAuto(event)
            }
         }
         event.preventDefault()
      },

      zoomAuto(event) {
         if (this.turnedOFF) return
         switch (this.scale) {
            case 1:
               this.scale = 2
               break
            case 2:
               this.scale = 4
               break
            default:
            case 4:
               this.scale = 1
               this.setCenter()
               break
         }
         this.setZoom()
         event.preventDefault()
      },
      wheelMove(event) {
         if (this.turnedOFF) return
         this.scale += -Math.sign(event.deltaY) * this.zoomStep
         this.setZoom()
      },
      touchMove(event) {
         if (this.turnedOFF) return
         event.preventDefault()
         if (this.lastX === null) {
            this.lastX = event.targetTouches[0].pageX
            this.lastY = event.targetTouches[0].pageY
            return
         }
         let step = this.$refs.imgex.width / 5
         if (event.targetTouches?.length === 2) {
            this.moveDisabled = true
            clearTimeout(this.disabledTimer)
            this.disabledTimer = setTimeout(
               () => (this.moveDisabled = false),
               this.moveDisabledTime
            )

            let p1 = event.targetTouches[0]
            let p2 = event.targetTouches[1]
            let touchDistance = Math.sqrt(
               Math.pow(p2.pageX - p1.pageX, 2) + Math.pow(p2.pageY - p1.pageY, 2)
            )
            if (!this.lastTouchDistance) {
               this.lastTouchDistance = touchDistance
               return
            }
            this.scale += (touchDistance - this.lastTouchDistance) / step
            this.lastTouchDistance = touchDistance
            this.setZoom()
         } else if (event.targetTouches.length === 1) {
            if (this.moveDisabled) return
            let x = event.targetTouches[0].pageX - this.lastX
            let y = event.targetTouches[0].pageY - this.lastY
            if (Math.abs(x) >= step && Math.abs(y) >= step) return
            this.lastX = event.targetTouches[0].pageX
            this.lastY = event.targetTouches[0].pageY
            this.doMove(x, y)
         }
      },
      setCenter() {
         let container = this.$refs.container
         let img = this.$refs.imgex

         this.position.center.x = Math.floor((container.clientWidth - img.clientWidth) / 2)
         this.position.center.y = Math.floor((container.clientHeight - img.clientHeight) / 2)

         img.style.left = this.position.center.x + "px"
         img.style.top = this.position.center.y + "px"
      },
      doMove(x, y) {
         let style = this.$refs.imgex.style
         let posX = this.pxStringToNumber(style.left) + x
         let posY = this.pxStringToNumber(style.top) + y

         style.left = posX + "px"
         style.top = posY + "px"

         this.position.relative.x = Math.abs(this.position.center.x - posX)
         this.position.relative.y = Math.abs(this.position.center.y - posY)

         if (posX < this.position.center.x) {
            this.position.relative.x = this.position.relative.x * -1
         }

         if (posY < this.position.center.y) {
            this.position.relative.y = this.position.relative.y * -1
         }
      },

      setZoom() {
         this.scale = this.scale < this.minScale ? this.minScale : this.scale
         this.scale = this.scale > this.maxScale ? this.maxScale : this.scale
         this.$refs.imgex.style.transform = `scale(${this.scale})`
      },

      pxStringToNumber(style) {
         return +style.replace("px", "")
      }
   }
}
</script>
<style scoped>
.image-ex-container {
 margin: auto;
 overflow: hidden;
 position: relative;
}

.image-ex-img {
 position: absolute;
}

.image-ex-img-center {
 left: 50%;
 top: 50%;
 transform: translate(-50%, -50%);
 position: absolute;
 transition: none;
}
</style>
