<template>
  <div id="login" :class="loginClass">
    <form @submit.prevent.stop="submit">
      <h1>&#8205;{{ text }}</h1>
      <div v-if="error !== ''" class="wrong">{{ error }}</div>

      <input
        autofocus
        type="text"
        autocapitalize="off"
        v-model="username"
        :placeholder="$t('login.username')"
      />
      <input
        type="password"
        v-model="password"
        :placeholder="$t('login.password')"
      />
      <input
        v-if="createMode"
        type="password"
        v-model="passwordConfirm"
        :placeholder="$t('login.passwordConfirm')"
      />

      <input
        type="submit"
        :value="createMode ? $t('login.signup') : $t('login.submit')"
      />

      <p @click="toggleMode" v-if="signup">
        {{
          createMode ? $t("login.loginInstead") : $t("login.createAnAccount")
        }}
      </p>
    </form>
  </div>
</template>

<script>
import * as auth from "@/utils/auth"
import { logoURL, name, signup } from "@/utils/constants"
import { useMainStore } from "@/stores/mainStore.js"
import { mapState } from "pinia"
import throttle from "lodash.throttle"
import { isMobile } from "@/utils/common.js"

export default {
   name: "login",
   computed: {
      ...mapState(useMainStore, ["user"]),
      signup: () => signup,
      name: () => name,
      logoURL: () => logoURL,
      loginClass() {
         let _ = this.refreshKey1
         if (this.isMobile()) return 'mobile'
         return 'desktop'
      },
   },
   data() {
      return {
         createMode: false,
         error: "",
         username: "",
         password: "",
         passwordConfirm: "",
         refreshKey1: 0,
         text: 'I Drive',
         sentences: [
            ['You look lonely', 2000, 0],  // [sentence, erase delay, next sentence delay]
            ['I can fix that~', 2000, 0],
            ['I Drive', 10000, 0],
         ],
         currentSentenceIndex: 0,
         typingDelay: 125,  // Delay between typing characters (ms)
         erasingDelay: 40,  // Delay between erasing characters (ms)
      }
   },
   watch: {
      username() {
         this.error = ""
      },
      password() {
         this.error = ""
      },
      passwordConfirm() {
         this.error = ""
      }
   },
   async mounted() {
      await this.$nextTick()
      this.setBackgroundImage()
      this.throttledResizeHandler = throttle(this.setBackgroundImage, 100)
      window.addEventListener("resize", this.throttledResizeHandler)
      setTimeout(() => {
         this.typeAndErase();
      }, 10)

   },
   unmounted() {
      window.removeEventListener("resize", this.throttledResizeHandler)
   },
   methods: {
      isMobile,
      toggleMode() {
         this.createMode = !this.createMode
      },
      typeAndErase() {
         const currentSentenceData = this.sentences[this.currentSentenceIndex];
         this.typeSentence(currentSentenceData[0], currentSentenceData[1], currentSentenceData[2]);
      },

      // Method to type a sentence
      typeSentence(sentence, eraseDelay, nextSentenceDelay) {
         let index = 0;
         let typedText = '';

         let minus = 0

         const typeInterval = setInterval(() => {
            // If the current character is a space, set the delay to 0
            if (sentence[index] === ' ') {
               typedText += ' ';
               this.text = typedText;
               index++;
               minus = this.typingDelay
               return; // Skip the delay for spaces
            }
            minus = 0

            // Otherwise, type the character with a delay
            typedText += sentence[index];
            this.text = typedText;
            index++;

            // When the sentence is fully typed, stop typing and start erasing
            if (index === sentence.length) {
               clearInterval(typeInterval);
               setTimeout(() => {
                  this.eraseSentence(eraseDelay, nextSentenceDelay);
               }, eraseDelay);
            }
         }, this.typingDelay - minus);
      },

      // Method to erase the current sentence
      eraseSentence(eraseDelay, nextSentenceDelay) {
         let currentText = this.text;
         const sentenceToErase = this.sentences[this.currentSentenceIndex][0];

         const eraseInterval = setInterval(() => {
            currentText = currentText.slice(0, -1);
            this.text = currentText;

            // When the sentence is fully erased, move to the next sentence
            if (currentText === '') {
               clearInterval(eraseInterval);
               this.moveToNextSentence(nextSentenceDelay);
            }
         }, this.erasingDelay);
      },

      // Method to move to the next sentence
      moveToNextSentence(nextSentenceDelay) {
         this.currentSentenceIndex = (this.currentSentenceIndex + 1) % this.sentences.length; // Loop through the sentences
         setTimeout(() => {
            this.typeAndErase();
         }, nextSentenceDelay); // Wait for the next sentence delay before starting the next cycle
      },

      setBackgroundImage() {
         this.refreshKey1 ++
         let element = document.querySelector("#login")
         if (isMobile()) {
            element.style.backgroundImage = "url('/img/wallpaper2.jpg')"
         } else {
            element.style.backgroundImage = "url('/img/wallpaper10.jpg')"

         }
      },
      submit: throttle(async function(event) {

         let redirect = this.$route.query.redirect

         if (this.createMode) {
            if (this.password !== this.passwordConfirm) {
               this.error = this.$t("login.passwordsDontMatch")
               return
            }
         }

         try {
            if (this.createMode) {
               await auth.signup(this.username, this.password)
            }

            await auth.login(this.username, this.password)
            if (redirect === "" || redirect === undefined || redirect === null) {
               redirect = `/files/${this.user.root}`
            }
            await this.$router.push({ path: redirect })

         } catch (e) {

            if (e.status === 409) {
               this.error = this.$t("login.usernameTaken")
            } else if (e.status === 400) {
               this.error = this.$t("login.wrongCredentials")
            } else if (e.status === 500) {
               this.error = this.$t("login.unexpectedError")
            } else if (e.status === 429) {
               this.error = this.$t("login.tooManyRequests")
            } else if (e.status === 403) {
               this.error = this.$t("login.notAllowed")
            } else {
               this.error = this.$t("login.unknownError")
               alert(e)
            }
         }
      }, 1000)
   }
}
</script>
<style scoped>
#login form {
 position: fixed;
 left: 50%;
 transform: translate(-50%, -50%);
 max-width: 16em;
 width: 90%;
}

#login .wrong {
 background: var(--red);
 color: #fff;
 padding: .5em;
 text-align: center;
 animation: .2s opac forwards;
}

@keyframes opac {
 0% {
  opacity: 0;
 }
 100% {
  opacity: 1;
 }
}

#login p {
 cursor: pointer;
 text-align: right;
 color: var(--blue);
 text-transform: lowercase;
 font-weight: 500;
 font-size: 0.9rem;
 margin: .5rem 0;
}

#login {
 position: fixed;
 top: 0;
 left: 0;
 width: 100%;
 height: 100%;
 background-size: cover;
 background-position: center;
}

#login h1 {
 text-align: center;
 font-size: 2.5em;
 margin: .4em 0 .67em;
 white-space: nowrap;

}

#login input::placeholder {
 color: white; /* Set the placeholder text color to white */
}

#login input {
 width: 100%;
 padding: 0.7em;
 border: none;
 outline: none;
 border-radius: 5px;
 background: rgba(0, 0, 0, 0.1);
}



/* =========== */
/* 📱  MOBILE   */
/* =========== */
#login.mobile form {
 top: 65%;
}

#login.mobile h1 {
 color: #fc2f99;
 text-shadow: 0 0 10px deeppink, 0 0 20px deeppink, 0 0 30px hotpink;
 font-weight: bold;
}

#login.mobile input[type='submit'] {
 background-color: rgba(255, 105, 180, 0.7);
 border: none;
 color: white;
 padding: 0.7em;
 font-size: 1em;
 cursor: pointer;
 transition: box-shadow 0.3s ease, background-color 0.3s ease;
 box-shadow: 0 0 6px rgba(255, 105, 180, 1);
}

#login.mobile input[type='submit']:hover {
 background-color: rgba(255, 105, 180, 0.8);
 box-shadow: 0 0 8px rgba(255, 105, 180, 0.5);
}

/* =========== */
/* 🖥️  MOBILE   */
/* =========== */
#login.desktop form {
 top: 48%;
}

#login.desktop h1 {
 color: #351B57ff;
 text-shadow: 0 0 10px #6B4EACff, 0 0 20px #776AB7ff, 0 0 30px #776AB7ff; /* Different shades of blue */
 font-weight: bold;
}

#login.desktop input[type='submit'] {
 background-color: rgb(111, 128, 180, 0.5);
 border: none;
 color: white;
 padding: 0.7em;
 font-size: 1em;
 cursor: pointer;
 transition: box-shadow 0.3s ease, background-color 0.3s ease;
 box-shadow: 0 0 6px rgb(111, 128, 180, 1);
}

#login.desktop input[type='submit']:hover {
 background-color: rgb(111, 128, 180, 0.8);
 box-shadow: 0 0 8px rgb(111, 128, 180, 0.5);
}

/* Change Autocomplete styles in Chrome */
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
textarea:-webkit-autofill,
textarea:-webkit-autofill:hover,
textarea:-webkit-autofill:focus,
select:-webkit-autofill,
select:-webkit-autofill:hover,
select:-webkit-autofill:focus {
 -webkit-text-fill-color: white;
 transition: background-color 50000s ease-in-out 0s;
 box-shadow: 0 0 8px rgba(255, 255, 255, 0.6);
}


</style>