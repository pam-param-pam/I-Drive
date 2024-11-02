<template>
  <div
    class="shell"
    :class="{ ['shell--hidden']: !showShell }"
    :style="{ height: `${this.shellHeight}em` }"
  >
    <div
      @pointerdown="startDrag()"
      @pointerup="stopDrag()"
      class="shell__divider"
      :style="this.shellDrag ? { background: `${checkTheme()}` } : ''"
    ></div>
    <div class="shell__content" ref="scrollable">
      <div v-for="(c, index) in content" :key="index" class="shell__result">
        <div class="shell__prompt">
          <i class="material-icons">chevron_right</i>
        </div>
        <pre class="shell__text">{{ c.text }}</pre>
      </div>

      <div
        class="shell__result"
        :class="{ 'shell__result--hidden': !canInput }"
      >
        <div class="shell__prompt">
          <i class="material-icons">chevron_right</i>
        </div>
        <pre
          tabindex="0"
          ref="input"
          class="shell__text"
          contenteditable="true"
          @keydown.prevent.38="historyUp"
          @keydown.prevent.40="historyDown"
          @keypress.prevent.enter="submit"
        />
      </div>
    </div>
    <div
      @pointerup="stopDrag()"
      class="shell__overlay"
      v-show="this.shellDrag"
    ></div>
  </div>
</template>

<script>
import {theme} from "@/utils/constants"
import throttle from "lodash.throttle"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"

export default {
   name: "shell",
   computed: {
      ...mapState(useMainStore, ["user", "showShell", "isFiles"]),
      path() {
         if (this.isFiles) {
            return this.$route.path
         }

         return ""
      },
   },
   data: () => ({
      websocket: null,
      content: [],
      history: [],
      historyPos: 0,
      canInput: false,
      shellDrag: false,
      shellHeight: 25,
      fontsize: parseFloat(getComputedStyle(document.documentElement).fontSize),
   }),

   mounted() {
      window.addEventListener("resize", this.resize)
      // let url = `${baseWS}/command`
      // let token = localStorage.getItem("token")
      //
      // this.websocket = new window.WebSocket(url, token)
      // let current_folder = store.state.currentFolder
      // this.websocket.onopen = () => this.canInput = true
      // this.websocket.onmessage = this.onMessage
      // this.websocket.onclose = this.onClose
      // // while (this.websocket.readyState !== 1) {
      // //
      // // }
      // this.websocket.send(JSON.stringify({"cmd_name": "test", "args": "Hello World!", working_dir_id: current_folder?.id}))
      // alert("1111")
   },

   beforeUnmount() {
      window.removeEventListener("resize", this.resize)
   },

   methods: {
      ...mapActions(useMainStore, ["toggleShell"]),

      checkTheme() {
         if (theme === "dark") {
            return "rgba(255, 255, 255, 0.4)"
         }
         return "rgba(127, 127, 127, 0.4)"
      },

      startDrag() {
         document.addEventListener("pointermove", this.handleDrag)
         this.shellDrag = true
      },

      stopDrag() {
         document.removeEventListener("pointermove", this.handleDrag)
         this.shellDrag = false
      },

      handleDrag: throttle(function (event) {
         const top = window.innerHeight / this.fontsize - 4
         const userPos = (window.innerHeight - event.clientY) / this.fontsize
         const bottom =
            2.25 +
            document.querySelector(".shell__divider").offsetHeight / this.fontsize

         if (userPos <= top && userPos >= bottom) {
            this.shellHeight = userPos.toFixed(2)
         }
      }, 32),

      resize: throttle(function () {
         const top = window.innerHeight / this.fontsize - 4
         const bottom =
            2.25 +
            document.querySelector(".shell__divider").offsetHeight / this.fontsize

         if (this.shellHeight > top) {
            this.shellHeight = top
         } else if (this.shellHeight < bottom) {
            this.shellHeight = bottom
         }
      }, 32),

      scroll() {
         this.$refs.scrollable.scrollTop = this.$refs.scrollable.scrollHeight
      },

      focusToEnd() {
         this.$nextTick(() => {
            const range = document.createRange()
            const selection = window.getSelection()
            range.selectNodeContents(this.$refs.input)
            range.collapse(false)
            selection.removeAllRanges()
            selection.addRange(range)
         })
      },

      historyUp() {
         if (this.historyPos > 0) {
            this.$refs.input.innerText = this.history[--this.historyPos]
            this.focusToEnd()

         }
      },

      historyDown() {
         if (this.historyPos >= 0 && this.historyPos < this.history.length - 1) {
            this.$refs.input.innerText = this.history[++this.historyPos]
            this.focusToEnd()
         } else {
            this.historyPos = this.history.length
            this.$refs.input.innerText = ""
         }
      },
      onClose() {
         // results.text = results.text
         //   // eslint-disable-next-line no-control-regex
         //   .replace(/\u001b\[[0-9;]+m/g, "") // Filter ANSI color for now
         //   .trimEnd()
         this.canInput = true
         this.$refs.input.focus()
         this.scroll()
      },
      onMessage(event) {
         results.text += `${event.data}\n`
         this.scroll()
      },
      submit(event) {
         let cmd = event.target.innerText.trim()

         if (cmd === "") {
            return
         }
         if (cmd === "clear") {
            this.content = []
            event.target.innerHTML = ""
            return
         }
         if (cmd === "exit") {
            event.target.innerHTML = ""
            this.toggleShell()
            return
         }

         this.canInput = false
         event.target.innerHTML = ""

         let results = {
            text: `${cmd}\n\n`,
         }

         this.history.push(cmd)
         this.historyPos = this.history.length
         this.content.push(results)


      },
   },
}
</script>
