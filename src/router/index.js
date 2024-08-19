import Vue from "vue"
import Router from "vue-router"
import Login from "@/views/Login.vue"
import Layout from "@/views/Layout.vue"

import store from "@/store"
// import Editor from "@/views/files/Editor.vue";
import Preview from "@/views/files/Preview.vue";
import Trash from "@/views/Trash.vue";


Vue.use(Router)


const router = new Router({
  base: "",
  mode: "history",
  routes: [
    {
      path: "/login",
      name: "Login",
      component: Login,
      beforeEnter: (to, from, next) => {
        if (store.getters.isLogged) {
          return next({ path: "/files" })
        }

        next()
      },
    },
    {
      path: "/*",
      component: Layout,
      children: [


        {
          path: "/share/:token/:folderId?",
          name: "Share",
          component: () => import('../views/Share.vue'),
          props: true,
          meta: {
            requiresAuth: false,
          },
        },

        {
          path: "/trash",
          name: "Trash",
          component: Trash,
          meta: {
            requiresAuth: true,
          },

        },
        {
          path: "/files/:folderId",
          name: "Files",
          component: () => import('../views/Files.vue'),
          props: true,
          meta: {
            requiresAuth: true,
          },

        },
        {
          path: "/editor/:folderId?/:fileId/:token", // kolejnosc tych dwóch Editor childrenów tu ma znaczenie :3
          name: "ShareEditor",
          // component: Editor,
          component: () => import('../views/files/Editor.vue'),
          props: true,
          meta: {
            requiresAuth: false,
          },

        },
        {
          path: "/editor/:fileId",
          name: "Editor",
          // component: Editor,
          component: () => import('../views/files/Editor.vue'),

          props: true,
          meta: {
            requiresAuth: true,
          },
        },
        {
          path: "/preview/:folderId?/:fileId/:token", // kolejnosc tych dwóch Preview childrenów tu ma znaczenie :3
          name: "SharePreview",
          component: Preview,
          props: true,
          meta: {
            requiresAuth: false,
          },

        },
        {
          path: "/preview/:fileId",
          name: "Preview",
          component: Preview,
          props: true,
          meta: {
            requiresAuth: true,
          },

        },
        {
          path: "/settings",
          name: "Settings",
          component: () => import('../views/Settings.vue'),
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
              component: () => import('../views/settings/Profile.vue'),

            },
            {
              path: "/settings/shares",
              name: "Shares",
              component: () => import('../views/settings/Shares.vue'),
            },

          ],
        },
        {
          path: "/403",
          name: "Forbidden",
          component: () => import('../views/Errors.vue'),
          props: {
            errorCode: 403,
            showHeader: true,
          },
        },
        {
          path: "/404",
          name: "NotFound",
          component: () => import('../views/Errors.vue'),
          props: {
            errorCode: 404,
            showHeader: true,
          },
        },
        {
          path: "/500",
          name: "InternalServerError",
          component: () => import('../views/Errors.vue'),
          props: {
            errorCode: 500,
            showHeader: true,
          },
        },
        {
          path: "/*",

          redirect: function(to) {
            if (store.state.user?.root) {
              return `/files/${store.state.user.root}`
            }
            else {
              return "/login"
            }
          }
        },
      ],
    },
  ],
})

router.beforeEach((to, from, next) => {

  if (to.matched.some((record) => record.meta.requiresAuth)) {
    if (!store.getters.isLogged) {
      next({
        path: "/login",
        query: { redirect: to.fullPath },
      })

      return
    }

    if (to.matched.some((record) => record.meta.requiresAdmin)) {
      if (!store.state.perms.admin) {
        next({ path: "/403" })
        return
      }
    }
  }

  next()
})


export default router
