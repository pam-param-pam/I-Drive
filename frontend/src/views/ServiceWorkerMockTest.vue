<template>
   <main class="sw-test-page">
      <h1>Service Worker Mock Test</h1>

      <video ref="videoRef" controls preload="metadata"></video>

      <div class="selector">
         <label>
            Encryption:
            <select v-model="selectedEncryption">
               <option value="aes">AES</option>
               <option value="chacha">ChaCha</option>
               <option value="null">Null / no encryption</option>
            </select>
         </label>
      </div>

      <div class="buttons">
         <button @click="registerServiceWorker">Register SW</button>
         <button @click="testVideoRoute">Set video.src = selected video</button>
         <button @click="downloadVideo" :disabled="isDownloading">Download selected video</button>
         <button @click="clearLogs">Clear SW logs</button>
         <button @click="unregisterServiceWorkers">Unregister SW</button>
      </div>

      <div v-if="isDownloading || downloadProgressPercent !== null" class="download-progress">
         <div class="progress-label">
            {{ downloadStatus }}
            <span v-if="downloadSpeed"> — {{ downloadSpeed }}</span>
         </div>

         <progress
           v-if="downloadProgressPercent !== null"
           :value="downloadProgressPercent"
           max="100"
         ></progress>

         <progress v-else></progress>
      </div>

      <div class="status">{{ status }}</div>

      <div class="sw-logs">
         <h2>Service Worker logs</h2>
         <pre>{{ swLogs.length ? swLogs.join('\n') : 'No logs yet.' }}</pre>
      </div>
   </main>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';

const videoRef = ref(null);
const status = ref('Initializing...');
const selectedEncryption = ref('aes');
const swLogs = ref([]);

const isDownloading = ref(false);
const downloadStatus = ref('');
const downloadProgressPercent = ref(null);

const videoRoute = computed(() => `/video/${selectedEncryption.value}`);
const downloadSpeed = ref('');
async function registerServiceWorker() {
   if (!('serviceWorker' in navigator)) {
      status.value = 'Service Worker not supported';
      return;
   }

   try {
      const registration = await navigator.serviceWorker.register('/empty_sw.js', { type: 'module', scope: '/' });
      await navigator.serviceWorker.ready;

      status.value = [
         'Service Worker registered',
         `Scope: ${registration.scope}`,
         `Controller active: ${navigator.serviceWorker.controller ? 'yes' : 'no'}`,
         '',
         'If controller active is "no", reload the page once.'
      ].join('\n');
   } catch (err) {
      status.value = `SW registration failed: ${err.message}`;
      console.error(err);
   }
}

function testVideoRoute() {
   if (!videoRef.value) return;

   videoRef.value.src = videoRoute.value;
   status.value = `video.src set to ${videoRoute.value}`;
}

async function downloadVideo() {
   downloadSpeed.value = '';
   if (!('showSaveFilePicker' in window)) {
      status.value = 'Streaming download to disk requires the File System Access API. Use Chrome/Edge on localhost or HTTPS.';
      return;
   }

   isDownloading.value = true;
   downloadProgressPercent.value = null;
   downloadStatus.value = 'Preparing download...';

   let writable;

   try {
      const fileHandle = await window.showSaveFilePicker({
         suggestedName: `video-${selectedEncryption.value}.mp4`,
         types: [
            {
               description: 'MP4 video',
               accept: {
                  'video/mp4': ['.mp4']
               }
            }
         ]
      });

      writable = await fileHandle.createWritable();

      const response = await fetch(videoRoute.value, {
         method: 'GET',
         cache: 'no-store'
      });

      if (!response.ok) {
         throw new Error(`Download failed: ${response.status} ${response.statusText}`);
      }

      if (!response.body) {
         throw new Error('Response body is not streamable');
      }

      const contentLengthHeader = response.headers.get('Content-Length');
      const totalBytes = contentLengthHeader ? Number(contentLengthHeader) : null;

      const reader = response.body.getReader();

      let receivedBytes = 0;
      let lastSpeedCheckTime = performance.now();
      let lastSpeedCheckBytes = 0;

      while (true) {
         const { done, value } = await reader.read();

         if (done) {
            break;
         }

         await writable.write(value);

         receivedBytes += value.byteLength;

         const now = performance.now();
         const elapsedMs = now - lastSpeedCheckTime;

         if (elapsedMs >= 500) {
            const bytesSinceLastCheck = receivedBytes - lastSpeedCheckBytes;
            const bytesPerSecond = bytesSinceLastCheck / (elapsedMs / 1000);

            downloadSpeed.value = `${formatBytes(bytesPerSecond)}/s`;

            lastSpeedCheckTime = now;
            lastSpeedCheckBytes = receivedBytes;
         }

         if (totalBytes && Number.isFinite(totalBytes) && totalBytes > 0) {
            downloadProgressPercent.value = Math.round((receivedBytes / totalBytes) * 100);
            downloadStatus.value = `Downloaded ${formatBytes(receivedBytes)} / ${formatBytes(totalBytes)} (${downloadProgressPercent.value}%)`;
         } else {
            downloadProgressPercent.value = null;
            downloadStatus.value = `Downloaded ${formatBytes(receivedBytes)}`;
         }
      }

      await writable.close();
      writable = null;

      downloadStatus.value = `Download complete: ${formatBytes(receivedBytes)}`;
      status.value = `Downloaded ${videoRoute.value}`;
   } catch (err) {
      if (writable) {
         try {
            await writable.abort();
         } catch {
            // ignore abort errors
         }
      }

      status.value = `Download failed: ${err.message}`;
      downloadStatus.value = `Download failed: ${err.message}`;
      console.error(err);
   } finally {
      downloadSpeed.value = '';
      isDownloading.value = false;
   }
}

async function unregisterServiceWorkers() {
   if (!('serviceWorker' in navigator)) return;

   const registrations = await navigator.serviceWorker.getRegistrations();

   for (const registration of registrations) {
      await registration.unregister();
   }

   status.value = 'All Service Workers unregistered. Reload the page.';
}

function handleServiceWorkerMessage(event) {
   if (event.data?.type !== 'SW_LOG') return;

   swLogs.value.unshift(`[${event.data.time}] ${event.data.message}`);

   if (swLogs.value.length > 100) {
      swLogs.value.pop();
   }
}

function clearLogs() {
   swLogs.value = [];
}

function formatBytes(bytes) {
   if (bytes < 1024) return `${bytes} B`;
   if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
   if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
   return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

onMounted(() => {
   status.value = 'Ready. Choose encryption type and click "Register SW".';

   if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', handleServiceWorkerMessage);
   }
});

onUnmounted(() => {
   if ('serviceWorker' in navigator) {
      navigator.serviceWorker.removeEventListener('message', handleServiceWorkerMessage);
   }
});
</script>

<style scoped>
.sw-test-page {
   font-family: system-ui;
   max-width: 800px;
   margin: 2rem auto;
   padding: 0 1rem;
}

video {
   width: 25%;
   background: #000;
   border-radius: 12px;
}

.selector {
   margin-top: 1rem;
}

select {
   margin-left: 0.5rem;
   padding: 0.4rem;
}

.buttons {
   margin-top: 1rem;
}

button {
   margin: 0.5rem;
   padding: 0.5rem 1rem;
   cursor: pointer;
}

button:disabled {
   cursor: not-allowed;
   opacity: 0.6;
}

.download-progress {
   margin-top: 1rem;
}

.progress-label {
   margin-bottom: 0.35rem;
   font-family: monospace;
}

progress {
   width: 100%;
   height: 1rem;
}

.status {
   background: var(--surfacePrimary);
   padding: 0.75rem;
   margin-top: 1rem;
   border-radius: 8px;
   white-space: pre-wrap;
   font-family: monospace;
}

.sw-logs {
   background: #111;
   color: #eee;
   padding: 0.75rem;
   margin-top: 1rem;
   border-radius: 8px;
   font-family: monospace;
   max-height: 300px;
   overflow-y: auto;
}

.sw-logs h2 {
   margin-top: 0;
   font-size: 1rem;
}

.sw-logs pre {
   white-space: pre-wrap;
   margin: 0;
}
</style>