import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import compression from 'vite-plugin-compression'

// https://vitejs.dev/config/
export default defineConfig({
  worker: {
    format: 'es'
  },
  plugins: [
    vue(),
    vueDevTools(),
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
})
