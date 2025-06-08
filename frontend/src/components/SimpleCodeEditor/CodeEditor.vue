<!--Package Name: Simple Code Editor-->
<!--Author: justcaliturner (https://github.com/justcaliturner)-->
<!--Copied in here to add theme dropdown and modify some other things-->

<template>
   <div
      :class="{
         'hide-header': !header,
         scroll: scroll,
         'read-only': readOnly,
         wrap: wrap
      }"
      :style="{
         width: width,
         height: height,
         zIndex: zIndex,
         maxWidth: maxWidth,
         minWidth: minWidth,
         maxHeight: maxHeight,
         minHeight: minHeight
      }"
      :theme="localTheme[0]"
      class="code-editor"
   >
      <div :style="{ borderRadius: borderRadius }" class="hljs">
         <div
            v-if="header"
            :class="{ border: showLineNums }"
            :style="{ borderRadius: borderRadius + ' ' + borderRadius + ' 0 0' }"
            class="header"
         >
            <CopyCode v-if="copyCode" @click="copy"></CopyCode>
            <saveButton
               v-if="saveFile"
               @click="$emit('saveFile')"
            ></saveButton>
            <closeButton @click="$emit('close')"></closeButton>

            <Dropdown
               v-if="displayLanguage"
               :defaultDisplay="langListDisplay"
               :disabled="themes.length <= 1"
               :title="localTheme[1]"
               :width="themeListWidth"
            >
               <ul :style="{ height: langListHeight }" class="lang-list hljs">
                  <li v-for="(lang, index) in themes" :key="index" @click="changeTheme(lang)">
                     {{ lang[1] ? lang[1] : lang[0] }}
                  </li>
               </ul>
            </Dropdown>
         </div>
         <div
            :style="{
               borderRadius: header ? '0 0 ' + borderRadius + ' ' + borderRadius : borderRadius
            }"
            class="code-area"
         >
            <div
               v-if="showLineNums"
               ref="lineNums"
               :style="{
                  fontSize: fontSize,
                  paddingTop: header ? '10px' : padding,
                  paddingBottom: padding,
                  top: top + 'px'
               }"
               class="line-nums hljs"
            >
               <div>1</div>
               <div v-for="num in lineNum">{{ num + 1 }}</div>
               <div>&nbsp;</div>
            </div>
            <textarea
               ref="textarea"
               :autofocus="autofocus"
               :readOnly="readOnly"
               :style="{
                  fontSize: fontSize,
                  padding: !header
                     ? padding
                     : lineNums
                       ? '10px ' + padding + ' ' + padding
                       : '0 ' + padding + ' ' + padding,
                  marginLeft: showLineNums ? lineNumsWidth + 'px' : '0',
                  width: showLineNums ? 'calc(100% - ' + lineNumsWidth + 'px)' : '100%'
               }"
               :value="modelValue === undefined ? content : modelValue"
               spellcheck="false"
               title="textarea"
               @input="updateValue"
               @scroll="calcScrollDistance"
               @keydown.tab.prevent.stop="tab"
            ></textarea>
            <pre
               :style="{
                  paddingRight: scrollBarWidth + 'px',
                  paddingBottom: scrollBarHeight + 'px',
                  marginLeft: showLineNums ? lineNumsWidth + 'px' : '0',
                  width: showLineNums ? 'calc(100% - ' + lineNumsWidth + 'px)' : '100%'
               }"
            >
        <code
          ref="code"
          v-highlight="contentValue"
          :class="languageClass"
          :style="{
            top: top + 'px',
            left: left + 'px',
            fontSize: fontSize,
            padding: !header ? padding : lineNums ? '10px ' + padding + ' ' + padding : '0 ' + padding + ' ' + padding,
          }">
        </code>
      </pre>
         </div>
      </div>
   </div>
</template>

<script>
import hljs from 'highlight.js'
import Dropdown from './Dropdown.vue'
import CopyCode from './CopyCode.vue'
import './themes/themes-base16.css'
import './themes/themes.css'
import SaveButton from '@/components/SimpleCodeEditor/SaveButton.vue'
import saveButton from '@/components/SimpleCodeEditor/SaveButton.vue'
import CloseButton from '@/components/SimpleCodeEditor/CloseButton.vue'

export default {
   components: {
      CloseButton,
      SaveButton,
      Dropdown,
      CopyCode
   },

   name: 'CodeEditor',

   emits: ['saveFile', 'close', 'theme', 'lang', 'update:modelValue', 'textarea', 'content'],

   props: {
      isSaveBtnLoading: {
         type: Boolean,
         default: false
      },
      lineNums: {
         type: Boolean,
         default: false
      },
      modelValue: {
         type: String
      },
      value: {
         type: String
      },
      theme: {
         type: Array,
         default: function () {
            return ['atom-one-dark', 'Atom One Dark']
         }
      },
      tabSpaces: {
         type: Number,
         default: 2
      },
      wrap: {
         type: Boolean,
         default: false
      },
      readOnly: {
         type: Boolean,
         default: false
      },
      autofocus: {
         type: Boolean,
         default: false
      },
      header: {
         type: Boolean,
         default: true
      },
      width: {
         type: String,
         default: '540px'
      },
      height: {
         type: String,
         default: 'auto'
      },
      maxWidth: {
         type: String
      },
      minWidth: {
         type: String
      },
      maxHeight: {
         type: String
      },
      minHeight: {
         type: String
      },
      borderRadius: {
         type: String,
         default: '12px'
      },
      languages: {
         type: Array,
         default: function () {
            return [['javascript', 'JS']]
         }
      },
      themes: {
         type: Array,
         default: function () {
            return [['atom-one-dark', 'Atom One Dark']]
         }
      },
      langListWidth: {
         type: String,
         default: '110px'
      },
      themeListWidth: {
         type: String,
         default: '150px'
      },
      langListHeight: {
         type: String,
         default: 'auto'
      },
      langListDisplay: {
         type: Boolean,
         default: false
      },
      displayLanguage: {
         type: Boolean,
         default: true
      },
      displayThemes: {
         type: Boolean,
         default: true
      },
      copyCode: {
         type: Boolean,
         default: true
      },
      saveFile: {
         type: Boolean,
         default: true
      },
      zIndex: {
         type: String,
         default: '0'
      },
      fontSize: {
         type: String,
         default: '17px'
      },
      padding: {
         type: String,
         default: '20px'
      }
   },

   created() {
      //we are registering vue language plugin
      function hljsDefineVue(e) {
         return {
            subLanguage: 'xml',
            contains: [
               e.COMMENT('\x3c!--', '--\x3e', {
                  relevance: 10
               }),
               {
                  begin: /^(\s*)(<script>)/gm,
                  end: /^(\s*)(<\/script>)/gm,
                  subLanguage: 'javascript',
                  excludeBegin: !0,
                  excludeEnd: !0
               },
               {
                  begin: /^(\s*)(<script lang=["']ts["']>)/gm,
                  end: /^(\s*)(<\/script>)/gm,
                  subLanguage: 'typescript',
                  excludeBegin: !0,
                  excludeEnd: !0
               },
               {
                  begin: /^(\s*)(<style(\sscoped)?>)/gm,
                  end: /^(\s*)(<\/style>)/gm,
                  subLanguage: 'css',
                  excludeBegin: !0,
                  excludeEnd: !0
               },
               {
                  begin: /^(\s*)(<style lang=["'](scss|sass)["'](\sscoped)?>)/gm,
                  end: /^(\s*)(<\/style>)/gm,
                  subLanguage: 'scss',
                  excludeBegin: !0,
                  excludeEnd: !0
               },
               {
                  begin: /^(\s*)(<style lang=["']stylus["'](\sscoped)?>)/gm,
                  end: /^(\s*)(<\/style>)/gm,
                  subLanguage: 'stylus',
                  excludeBegin: !0,
                  excludeEnd: !0
               }
            ]
         }
      }

      hljs.registerLanguage('vue', hljsDefineVue)
   },

   directives: {
      highlight: {
         mounted(el, binding) {
            el.textContent = binding.value

            hljs.highlightElement(el)
         },
         updated(el, binding) {
            if (el.scrolling) {
               el.scrolling = false
            } else {
               el.textContent = binding.value
               hljs.highlightElement(el)
            }
         }
      }
   },

   data() {
      return {
         scrollBarWidth: 0,
         scrollBarHeight: 0,
         top: 0,
         left: 0,
         localTheme: this.theme,
         languageClass: 'hljs language-' + this.languages[0][0],
         languageTitle: this.languages[0][1] ? this.languages[0][1] : this.languages[0][0],
         content: this.value,
         cursorPosition: 0,
         insertTab: false,
         lineNum: 0,
         lineNumsWidth: 0,
         scrolling: false,
         textareaHeight: 0,
         showLineNums: this.wrap ? false : this.lineNums
      }
   },

   computed: {
      saveButton() {
         return saveButton
      },
      tabWidth() {
         let result = ''
         for (let i = 0; i < this.tabSpaces; i++) {
            result += ' '
         }
         return result
      },
      contentValue() {
         return this.modelValue === undefined ? this.content + '\n' : this.modelValue + '\n'
      },
      scroll() {
         return this.height !== 'auto'
      }
   },

   methods: {
      updateValue(e) {
         if (this.modelValue === undefined) {
            this.content = e.target.value
         } else {
            this.$emit('update:modelValue', e.target.value)
         }
      },

      changeTheme(theme) {
         this.localTheme = theme

         this.$emit('theme', theme[0])
      },

      tab() {
         if (document.execCommand('insertText')) {
            document.execCommand('insertText', false, this.tabWidth)
         } else {
            const cursorPosition = this.$refs.textarea.selectionStart
            this.content =
               this.content.substring(0, cursorPosition) +
               this.tabWidth +
               this.content.substring(cursorPosition)
            this.cursorPosition = cursorPosition + this.tabWidth.length
            this.insertTab = true
         }
      },

      calcScrollDistance(e) {
         this.$refs.code.scrolling = true
         this.scrolling = true
         this.top = -e.target.scrollTop
         this.left = -e.target.scrollLeft
      },

      resizer() {
         // textareaResizer
         const textareaResizer = new ResizeObserver((entries) => {
            this.scrollBarWidth = entries[0].target.offsetWidth - entries[0].target.clientWidth
            this.scrollBarHeight = entries[0].target.offsetHeight - entries[0].target.clientHeight
            this.textareaHeight = entries[0].target.offsetHeight
         })
         textareaResizer.observe(this.$refs.textarea)
         // lineNumsResizer
         const lineNumsResizer = new ResizeObserver((entries) => {
            this.lineNumsWidth = entries[0].target.offsetWidth
         })
         if (this.$refs.lineNums) {
            lineNumsResizer.observe(this.$refs.lineNums)
         }
      },

      copy() {
         if (document.execCommand('copy')) {
            this.$refs.textarea.select()
            document.execCommand('copy')
            window.getSelection().removeAllRanges()
         } else {
            navigator.clipboard.writeText(this.$refs.textarea.value)
         }
      },

      getLineNum() {
         // lineNum
         const str = this.$refs.textarea.value
         let lineNum = 0
         let position = str.indexOf('\n')
         while (position !== -1) {
            lineNum++
            position = str.indexOf('\n', position + 1)
         }
         // heightNum
         const singleLineHeight = this.$refs.lineNums.firstChild.offsetHeight
         const heightNum = parseInt(this.textareaHeight / singleLineHeight) - 1
         // displayed lineNum
         this.lineNum = this.height === 'auto' ? lineNum : lineNum > heightNum ? lineNum : heightNum
      }
   },

   mounted() {
      this.$emit('lang', this.languages[0][0])
      this.$emit('content', this.content)
      this.$emit('textarea', this.$refs.textarea)
      this.resizer()
   },

   updated() {
      if (this.insertTab) {
         this.$refs.textarea.setSelectionRange(this.cursorPosition, this.cursorPosition)
         this.insertTab = false
      }
      if (this.lineNums) {
         if (this.scrolling) {
            this.scrolling = false
         } else {
            this.getLineNum()
         }
      }
   }
}
</script>

<style scoped>
.code-editor {
   position: relative;
}

.code-editor > div {
   width: 100%;
   height: 100%;
}

/* header */
.code-editor .header {
   box-sizing: border-box;
   position: relative;
   z-index: 1;
   height: 50px;
}

.code-editor .header > .dropdown {
   position: absolute;
   top: 17px;
   right: 107px;
}

.code-editor .header > .copy-code {
   position: absolute;
   top: 13px;
   right: 12px;
}

.code-editor .header > .save-file {
   position: absolute;
   top: 13px;
   right: 60px;
}

.code-editor .header > .close-button {
   position: absolute;
   top: 10px;
   left: 10px;
}

/* code-area */
.code-editor .code-area {
   position: relative;
   z-index: 0;
   text-align: left;
   overflow: hidden;
}

/* font style */
.code-editor .code-area > textarea,
.code-editor .code-area > pre > code,
.code-editor .line-nums > div {
   font-family: Consolas, Monaco, monospace;
   line-height: 1.5;
}

.code-editor .code-area > textarea:hover,
.code-editor .code-area > textarea:focus-visible {
   outline: none;
}

.code-editor .code-area > textarea {
   position: absolute;
   z-index: 1;
   top: 0;
   left: 0;
   overflow-y: hidden;
   box-sizing: border-box;
   caret-color: rgb(127, 127, 127);
   color: transparent;
   white-space: pre;
   word-wrap: normal;
   border: 0;
   width: 100%;
   height: 100%;
   background: none;
   resize: none;
}

.code-editor .code-area > pre {
   box-sizing: border-box;
   position: relative;
   z-index: 0;
   overflow: hidden;
   font-size: 0;
   margin: 0;
}

.code-editor .code-area > pre > code {
   background: none;
   display: block;
   position: relative;
   overflow-x: visible !important;
   border-radius: 0;
   box-sizing: border-box;
   margin: 0;
}

/* wrap code */
.code-editor.wrap .code-area > textarea,
.code-editor.wrap .code-area > pre > code {
   white-space: pre-wrap;
   word-wrap: break-word;
}

/* hide-header */
.code-editor.hide-header.scroll .code-area {
   height: 100%;
}

/* scroll */
.code-editor.scroll .code-area {
   height: calc(100% - 34px);
}

.code-editor.scroll .code-area > textarea {
   overflow: auto;
}

.code-editor.scroll .code-area > pre {
   width: 100%;
   height: 100%;
   overflow: hidden;
}

/* dropdown */
.code-editor .list {
   -webkit-user-select: none;
   user-select: none;
   height: 100%;
   font-family: sans-serif;
}

.code-editor .list > .lang-list {
   border-radius: 5px;
   box-sizing: border-box;
   overflow: auto;
   font-size: 13px;
   padding: 0;
   margin: 0;
   list-style: none;
   text-align: left;
}

.code-editor .list > .lang-list > li {
   font-size: 13px;
   transition:
      background 0.16s ease,
      color 0.16s ease;
   box-sizing: border-box;
   padding: 0 12px;
   white-space: nowrap;
   overflow: hidden;
   text-overflow: ellipsis;
   line-height: 30px;
}

.code-editor .list > .lang-list > li:first-child {
   padding-top: 5px;
}

.code-editor .list > .lang-list > li:last-child {
   padding-bottom: 5px;
}

.code-editor .list > .lang-list > li:hover {
   background: rgba(160, 160, 160, 0.4);
}

/* line-nums */
.code-editor .line-nums {
   min-width: 36px;
   text-align: right;
   box-sizing: border-box;
   position: absolute;
   left: 0;
   padding-right: 8px;
   padding-left: 8px;
   opacity: 0.3;
}

.code-editor .line-nums::after {
   content: '';
   position: absolute;
   width: 100%;
   height: 100%;
   top: 0;
   left: 0;
   border-right: 1px solid currentColor;
   opacity: 0.5;
}

.code-editor .header.border::after {
   content: '';
   position: absolute;
   width: 100%;
   height: 1px;
   bottom: 0;
   left: 0;
   background: currentColor;
   opacity: 0.15;
}

.code-editor::-webkit-scrollbar {
   width: 8px;
   height: 8px;
}

.code-editor::-webkit-scrollbar-track {
   border-radius: 10px;
}

.code-editor::-webkit-scrollbar-thumb {
   background-color: #dcdcdc;
   border-radius: 12px;
   border: 2px solid currentColor;
}

.code-editor {
   scrollbar-width: thin;
   scrollbar-color: #dcdcdc currentColor;
}
</style>
