<template>
  <div id="login">
    <form @submit.prevent.stop="submit">
      <img :src="logoURL" :alt="name"/>
      <h1>{{ name }}</h1>
      <div v-if="error !== ''" class="wrong">{{ error }}</div>

      <input
        autofocus
        class="input input--block"
        type="text"
        autocapitalize="off"
        v-model="username"
        :placeholder="$t('login.username')"
      />
      <input
        class="input input--block"
        type="password"
        v-model="password"
        :placeholder="$t('login.password')"
      />
      <input
        class="input input--block"
        v-if="createMode"
        type="password"
        v-model="passwordConfirm"
        :placeholder="$t('login.passwordConfirm')"
      />

      <input
        class="button button--block"
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
import {logoURL, name, signup,} from "@/utils/constants"
import {useMainStore} from "@/stores/mainStore.js"
import {mapState} from "pinia"
import throttle from "lodash.throttle"

export default {
   name: "login",
   computed: {
      ...mapState(useMainStore, ["user"]),
      signup: () => signup,
      name: () => name,
      logoURL: () => logoURL,
   },
   data() {
      return {
         createMode: false,
         error: "",
         username: "",
         password: "",
         passwordConfirm: "",
      }
   },
   watch: {
      username() { this.error = "" },
      password() { this.error = ""},
      passwordConfirm() { this.error = "" },
   },
   methods: {
      toggleMode() {
         this.createMode = !this.createMode
      },

      submit: throttle(async function (event) {

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
            await this.$router.push({path: redirect})

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
   },
}
</script>
