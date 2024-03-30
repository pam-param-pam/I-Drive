import Vue from "vue";
import Router from "vue-router";
import Login from "@/views/Login.vue";
import Layout from "@/views/Layout.vue";
import Files from "@/views/Files.vue";
import Share from "@/views/Share.vue";
import Settings from "@/views/Settings.vue";
import ProfileSettings from "@/views/settings/Profile.vue";
import Shares from "@/views/settings/Shares.vue";
import Errors from "@/views/Errors.vue";
import store from "@/store";
import Player from "@/views/files/player.vue";
import { baseURL, name } from "@/utils/constants";
import i18n, { rtlLanguages } from "@/i18n";
import Listing from "@/views/files/Listing.vue";
import Preview from "@/views/files/Preview.vue";
import Editor from "@/views/files/Editor.vue";
import Trash from "@/views/Trash.vue";

Vue.use(Router);


const router = new Router({
  base: import.meta.env.PROD ? baseURL : "",
  mode: "history",
  routes: [
    {
      path: "/login",
      name: "Login",
      component: Login,
      beforeEnter: (to, from, next) => {
        if (store.getters.isLogged) {
          return next({ path: "/files" });
        }

        next();
      },
    },
    {
      path: "/*",
      component: Layout,
      children: [
        {
          path: "/share/*",
          name: "Share",
          component: Share,
        },
        {
          path: "/trash",
          name: "Trash",
          component: Trash,
        },
        {
          path: "/files",
          name: "Files",
          component: Files,
          meta: {
            requiresAuth: true,
          },
          children: [
            {
              path: "/folder/:folderId",
              name: "Listing",
              component: Listing,

            },
            {
              path: "/preview/:fileId",
              name: "Preview",
              component: Preview,

            },
            {
              path: "/editor/:fileId",
              name: "Editor",
              component: Editor,

            },

          ],
        },

        {
          path: "/player/:fileId",
          name: "Player",
          component: Player,
          meta: {
            requiresAuth: true,
          },
        },
        {
          path: "/settings",
          name: "Settings",
          component: Settings,
          redirect: {
            path: "/settings/profile",
          },
          meta: {
            requiresAuth: true,
          },
          children: [
            {
              path: "/settings/profile",
              name: "ProfileSettings",
              component: ProfileSettings,
            },
            {
              path: "/settings/shares",
              name: "Shares",
              component: Shares,
            },

          ],
        },
        {
          path: "/403",
          name: "Forbidden",
          component: Errors,
          props: {
            errorCode: 403,
            showHeader: true,
          },
        },
        {
          path: "/404",
          name: "NotFound",
          component: Errors,
          props: {
            errorCode: 404,
            showHeader: true,
          },
        },
        {
          path: "/500",
          name: "InternalServerError",
          component: Errors,
          props: {
            errorCode: 500,
            showHeader: true,
          },
        },
        {
          path: "/*",
          redirect: (to) => `/files`,
        },
      ],
    },
  ],
});

router.beforeEach((to, from, next) => {


  /*** RTL related settings per route ****/

  const rtlSet = document.querySelector("body").classList.contains("rtl");
  const shouldSetRtl = rtlLanguages.includes(i18n.locale);
  switch (true) {
    case shouldSetRtl && !rtlSet:
      document.querySelector("body").classList.add("rtl");
      break;
    case !shouldSetRtl && rtlSet:
      document.querySelector("body").classList.remove("rtl");
      break;
  }

  if (to.matched.some((record) => record.meta.requiresAuth)) {
    if (!store.getters.isLogged) {
      next({
        path: "/login",
        query: { redirect: to.fullPath },
      });

      return;
    }

    if (to.matched.some((record) => record.meta.requiresAdmin)) {
      if (!store.state.perms.admin) {
        next({ path: "/403" });
        return;
      }
    }
  }

  next();
});


export default router;
