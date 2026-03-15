import { createRouter, createWebHistory } from "vue-router"
import Trash from "@/views/Trash.vue"
import Layout from "@/views/Layout.vue"

import { useMainStore } from "@/stores/mainStore.js"
import { validateLogin } from "@/utils/auth.js"
import { deviceControl } from "@/utils/deviceControl.js"
import { lazyWithLoading } from "@/utils/common.js"


const router = createRouter({

   history: createWebHistory(import.meta.env.BASE_URL),
   routes: [
      {
         path: "/login",
         name: "Login",
         component: () => import("../views/Login.vue"),
         beforeEnter: async (to, from, next) => {
            const store = useMainStore()
            if (store.user == null) {
               await initAuth()
            }

            if (store.isLogged) {
               return next({ name: "Files", params: { folderId: store.user.root } })
            }

            next()
         }
      },
      {
         path: "/*",
         component: Layout,
         children: [
            {
               path: "/share/:token/:folderId?",
               name: "Share",
               component: () => import("../views/Share.vue"),
               props: route => ({
                  token: route.params.token,
                  folderId: route.params.folderId
               }),
               meta: {
                  requiresAuth: false
               },
               children: [
                  {
                     path: "editor/:fileId", // The order of these two Editor children matters :3
                     name: "ShareEditor",
                     component: lazyWithLoading(() => import("../views/Editor.vue")),
                     props: true,
                     meta: {
                        requiresAuth: false
                     }
                  },

                  {
                     path: "preview/:fileId", // kolejnosc tych dwóch Preview childrenów tu ma znaczenie :3
                     name: "SharePreview",
                     component: lazyWithLoading(() => import("../views/Preview.vue")),
                     props: true,
                     meta: {
                        requiresAuth: false
                     }

                  },
               ]
            },
            {
               path: "/trash",
               name: "Trash",
               component: Trash,  // idk why but lazy loading this doesnt work, css gets messed up, very weaird
               meta: {
                  requiresAuth: true
               }

            },
            {
               path: "/files/:folderId/:lockFrom?",
               name: "Files",
               component: () => import("../views/Files.vue"),
               props: true,
               meta: {
                  requiresAuth: true
               },
               children: [
                  {
                     path: "preview/:fileId",
                     name: "Preview",
                     component: lazyWithLoading(() => import("../views/Preview.vue")),
                     props: true,
                     meta: {
                        requiresAuth: true
                     }
                  },
                  {
                     path: "editor/:fileId",
                     name: "Editor",
                     component: lazyWithLoading(() => import("../views/Editor.vue")),

                     props: true,
                     meta: {
                        requiresAuth: true
                     }
                  },
               ]
            },
            {
               path: "/settings",
               name: "Settings",
               component: () => import("../views/Settings.vue"),
               redirect: {
                  path: "/settings/profile"
               },
               meta: {
                  requiresAuth: true
               },
               children: [
                  {
                     path: "/settings/profile",
                     name: "Profile",
                     component: () => import("../views/settings/Profile.vue")

                  },
                  {
                     path: "/settings/shares",
                     name: "Shares",
                     component: () => import("../views/settings/Shares.vue")
                  },
                  {
                     path: "/settings/discord",
                     name: "DiscordSettings",
                     component: () => import("../views/settings/Discord.vue")
                  },
                  {
                     path: "/settings/devices",
                     name: "ActiveDevices",
                     component: () => import("../views/settings/Devices.vue")
                  }
               ]
            }
         ]
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
               return next({ name: "Login" })
            }

            return next({ name: "Files", params: { folderId: store.user.root } })
         }
      }

   ]
})


async function initAuth() {
   // todo this func is called in 3 places, sometimes twice
   try {
      await validateLogin()
   } catch (error) {
      console.error(error)
   }
}


router.beforeEach((to, from, next) => {
   const store = useMainStore()

    if (store.currentPrompt) {
      store.closeHover()
      next(false) // consume back
      return
   }
   next()
})

router.afterEach((to, from) => {
   const routeForPush = {
      name: to.name,
      params: { ...to.params },
      query: { ...to.query }
   }
   deviceControl.sendRouteChangeEvent(routeForPush)
})

router.beforeResolve(async (to, from, next) => {
   const store = useMainStore()
   store.closeHovers()
   store.resetSelected()
   store.setError(null)
   store.setMultiSelection(false)
   store.closeContextMenu()
   // this will only be null on first route
   if (from.name == null) {
      await initAuth()
   }

   if (to.matched.some((record) => record.meta.requiresAuth)) {
      if (!store.isLogged) {
         next({
            path: "/login"
         })

         return
      }

      if (to.matched.some((record) => record.meta.requiresAdmin)) {
         if (!store.perms.admin) {
            next({ path: "/403" })
            return
         }
      }
   }

   next()
})
export default router
