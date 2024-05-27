import "whatwg-fetch"
import cssVars from "css-vars-ponyfill"
import { sync } from "vuex-router-sync"
import store from "@/store"
import router from "@/router"
import i18n from "@/i18n"
import Vue from "@/utils/vue"
import {loginPage } from "@/utils/constants"
import { login, validateLogin } from "@/utils/auth"
import App from "@/App.vue"
import onEvent from "@/utils/WsEventhandler.js"

cssVars()

sync(store, router)

async function start() {
  try {
    if (loginPage) {
      await validateLogin()
    } else {
      await login("", "",)
    }
  } catch (e) {
    //ignore cuz the login validation is done under the hood,
    // so if the error is thrown, it's already handled by other parts of the code
    // and to be precise, the ones that redirect to log-in when 403 or token/settings/user is null or incorrect.
    // don't tell me it's stupid - I didn't createShare this system lol

  }


  new Vue({
    el: "#app",
    store,
    router,
    i18n,
    template: "<App/>",
    components: { App },
    mounted() {
      this.$options.sockets.onmessage = (data) => onEvent(data)


    }
  })
}

start()
