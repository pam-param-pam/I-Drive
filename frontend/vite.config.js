import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import compression from 'vite-plugin-compression'
import path from "node:path"

function devServiceWorkerPlugin() {
  return {
    name: "dev-service-worker",
    configureServer(server) {
      server.middlewares.use("/service_worker.js", async (req, res) => {
        try {
          const swPath = path.resolve(__dirname, "src/service-worker/service_worker.js")
          const result = await server.transformRequest(swPath)

          res.setHeader("Content-Type", "application/javascript")
          res.setHeader("Cache-Control", "no-store")
          res.end(result.code)
        } catch (err) {
          res.statusCode = 500
          res.end(String(err.stack || err.message))
        }
      })
    }
  }
}

export default defineConfig({
  worker: {
    format: 'es'
  },
  plugins: [
    vue(),
    vueDevTools(),
    devServiceWorkerPlugin(),
    compression({
      algorithm: 'gzip',
      ext: '.gz',
      threshold: 1024,
      deleteOriginFile: false
    })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      jsmediatags: "jsmediatags/dist/jsmediatags.min.js",
    },
  },
  build: {
    rollupOptions: {
      input: {
        app: path.resolve(__dirname, "index.html"),
        service_worker: path.resolve(__dirname, "src/service-worker/service_worker.js")
      },

      output: {
        entryFileNames(chunkInfo) {
          if (chunkInfo.name === "service_worker") {
            return "service_worker.js"
          }

          return "assets/[name]-[hash].js"
        },

        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    },
  }
})
