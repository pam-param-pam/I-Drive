import {createRouter, createWebHistory} from 'vue-router'
import Preview from "@/views/files/Preview.vue"
import Trash from "@/views/Trash.vue"
import Layout from "@/views/Layout.vue"
import Login from "@/views/Login.vue"

import {useMainStore} from "@/stores/mainStore.js"
import {validateLogin} from "@/utils/auth.js"
import VueNativeSock from "vue-native-websocket-vue3"
import {baseWS} from "@/utils/constants.js"
import app from "@/main.js"
import onEvent from "@/utils/WsEventhandler.js"


const router = createRouter({

   history: createWebHistory(import.meta.env.BASE_URL),
   routes: [
      {
         path: "/login",
         name: "Login",
         component: Login,
         beforeEnter: async (to, from, next) => {
            const store = useMainStore()
            if (store.user == null) {
               await initAuth()
            }

            if (store.isLogged) {
               return next({name: 'Files', params: {folderId: store.user.root}})
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
         path: "/:catchAll(.*)",
         name: "catchAll",

         beforeEnter: async (to, from, next) => {

            const store = useMainStore()

            if (store.user == null) {
               await initAuth()
            }

            if (!store.isLogged) {
               // If not authenticated, you might want to redirect them to a login page or handle it accordingly
               // For example, redirect to a login page:
               return next({name: 'Login'}) // Adjust this to your login route if necessary
            }

            // If authenticated, redirect to the Files route with a specific folderId
            // Replace 'someFolderId' with the appropriate logic to determine the folderId
            return next({name: 'Files', params: {folderId: store.user.root}})
         }
      },

   ],
})

async function initAuth() {
   try {
      await validateLogin()
   } catch (error) {
      console.error(error)
   }
   const token = localStorage.getItem("token")

   app.use(VueNativeSock, baseWS + "/user", {reconnection: false, protocol: token})

   app.config.globalProperties.$socket.onmessage = (data) => onEvent(data)

   console.error("INIT AUTH")
   console.log(app)
   console.log(app.config.globalProperties.$socket)
}

router.beforeResolve(async (to, from, next) => {
   console.log("BEFORE RESOLVE")
   const store = useMainStore()
   store.closeHovers()
   store.resetSelected()
   // this will only be null on first route
   if (from.name == null) {
      await initAuth()
   }

   if (to.matched.some((record) => record.meta.requiresAuth)) {
      if (!store.isLogged) {
         next({
            path: "/login",
            query: {redirect: to.fullPath},
         })

         return
      }

      if (to.matched.some((record) => record.meta.requiresAdmin)) {
         if (!store.perms.admin) {
            next({path: "/403"})
            return
         }
      }
   }

   next()
})
export default router
