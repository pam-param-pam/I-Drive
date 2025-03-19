<template>
  <div
    :class="{ ['shell--hidden']: !showShell }"
    :style="{ height: `${this.shellHeight}em` }"
    class="shell"
    @click="focusInput"
  >
    <div
      :style="this.shellDrag ? { background: `${checkTheme()}` } : ''"
      class="shell__divider"
      @pointerdown="startDrag()"
      @pointerup="stopDrag()"
    ></div>
    <div ref="scrollable" class="shell__content">
      <div v-for="(c, index) in shellSettings.shellContent" :key="index" class="shell__result">
        <div class="shell__prompt">
          <i class="material-icons">chevron_right</i>
        </div>
        <pre class="shell__text" :class="getTextColorClass(c.type)">{{ c.text }}</pre>
      </div>

      <div :class="{ 'shell__result': !canInput }" class="shell__result">
        <div class="shell__prompt">
          <i class="material-icons">chevron_right</i>
        </div>
        <pre
          ref="input"
          class="shell__text"
          contenteditable="true"
          tabindex="0"
          @keydown.prevent.up="historyUp"
          @keydown.prevent.down="historyDown"
          @keypress.prevent.enter="submit"
        />
      </div>
    </div>
    <div v-show="this.shellDrag" class="shell__overlay" @pointerup="stopDrag()"></div>
  </div>
</template>

<script>
import { theme } from "@/utils/constants"
import throttle from "lodash.throttle"
import { useMainStore } from "@/stores/mainStore.js"
import { mapActions, mapState } from "pinia"

export default {
   name: "shell",

   computed: {
      ...mapState(useMainStore, ["user", "showShell", "isFiles", "shellSettings", "items"])
   },

   data() {
      return {
         websocket: null,
         history: [],
         historyPos: 0,
         canInput: false,
         shellDrag: false,
         shellHeight: 25,
         fontsize: parseFloat(getComputedStyle(document.documentElement).fontSize)
      }
   },

   async mounted() {
      window.addEventListener("resize", this.resize)
      this.scroll()

   },

   beforeUnmount() {
      window.removeEventListener("resize", this.resize)
   },
   watch: {
      "shellSettings.shellContent": {
         async handler(newValue, oldValue) {
            await this.$nextTick()
            this.scroll()
         },
      },
      showShell(newValue) {
         if (newValue) {
            // Autofocus input when shell is opened
            this.$nextTick(() => {
               this.focusInput()
            });
         }
      }
   },
   methods: {
      ...mapActions(useMainStore, ["toggleShell", "setShellSettings", "pushShellContent", "clearShellContent", "setItems"]),
      focusInput() {
         this.$refs.input?.focus()
      },
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

      handleDrag: throttle(function(event) {
         const top = window.innerHeight / this.fontsize - 4
         const userPos = (window.innerHeight - event.clientY) / this.fontsize
         const bottom =
            2.25 + document.querySelector(".shell__divider").offsetHeight / this.fontsize

         if (userPos <= top && userPos >= bottom) {
            this.shellHeight = userPos.toFixed(2)
         }
         this.scroll()

      }, 32),

      resize: throttle(function() {
         const top = window.innerHeight / this.fontsize - 4
         const bottom =
            2.25 + document.querySelector(".shell__divider").offsetHeight / this.fontsize

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
      getTextColorClass(type) {
         return {
            "text-log": type === "log",
            "text-warn": type === "warn",
            "text-error": type === "error",
            "text-success": type === "success"
         }
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
            this.clearContent()
            event.target.innerHTML = ""
            return
         }
         if (cmd === "exit") {
            event.target.innerHTML = ""
            this.toggleShell()
            return
         }
         this.pushContent(cmd)

         if (cmd === "set") {
            let shellSettings = { ...this.shellSettings }
            shellSettings["showFileInfoInSidebar"] = !shellSettings["showFileInfoInSidebar"]
            this.setShellSettings(shellSettings)
            this.pushContent(cmd)
            this.pushContent("toggled", "success")
            return
         }
         if (cmd === "ls") {
            this.items.forEach((item) => {
               this.pushContent( item.name)
            })
         }
         if (cmd === "sudo hack obama") {
            this.pushContent( "Hacking main frame...", "success")
            this.pushContent( "...", "success")
            this.pushContent( "ERROR", "warn")
            this.pushContent( "Incoming missiles", "error")
         }
         if (cmd.startsWith("eval")) {
            try {
               eval(cmd.replace("eval ", ""));
            } catch (error) {
               this.pushContent( `Error: ${error.message}`, "error")
            }
         }
         this.canInput = false
         event.target.innerHTML = ""

         this.history.push(cmd)
         this.historyPos = this.history.length
      },
      pushContent(cmd, type = "log") {
         this.pushShellContent({ text: cmd, type: type })
         this.scroll()

      },
      clearContent() {
         this.clearShellContent()
      }
   }
}
</script>
<style scoped>
.text-error {
 color: red;
}

.text-warn {
 color: orange;
}

.text-log {
 color: var(--textPrimary);
}

.text-success {
 color: var(--textSecondary);
}
</style>