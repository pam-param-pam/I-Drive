import {createRouter, createWebHistory} from 'vue-router'
import Trash from "@/views/Trash.vue"
import Layout from "@/views/Layout.vue"
import Login from "@/views/Login.vue"

import {useMainStore} from "@/stores/mainStore.js"
import {validateLogin} from "@/utils/auth.js"
import Preview from "@/views/Preview.vue"

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
               path: "/files/:folderId/:lockFrom?",
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
               component: () => import('../views/Editor.vue'),
               props: true,
               meta: {
                  requiresAuth: false,
               },

            },
            {
               path: "/editor/:fileId",
               name: "Editor",
               // component: Editor,
               component: () => import('../views/Editor.vue'),

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
                  {
                     path: "/settings/discord",
                     name: "DiscordSettings",
                     component: () => import('../views/settings/Discord.vue'),
                  },
               ],
            },
         ],
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
               return next({name: 'Login'})
            }

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
}

router.beforeResolve(async (to, from, next) => {
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
