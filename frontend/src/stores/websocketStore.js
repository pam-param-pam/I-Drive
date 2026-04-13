import { defineStore } from "pinia"

function createState() {
   return {
      socket: null,
      url: null,
      status: "idle", // idle | connecting | open | closed | error

      // heartbeat
      lastPing: 0,
      pingTimeout: 150000,
      pingIntervalId: null,

      // reconnect
      reconnectAttempts: 0,
      reconnectTimer: null,

      // listeners
      listeners: new Set()
   }
}

export const useWebSocketStore = defineStore("websocket", {
   state: () => ({
      sockets: {} // key -> state
   }),

   actions: {

      // ---------- PUBLIC API ----------

      connect(key, url, token) {
         const state = this._ensure(key)

         // if same URL and already open → ignore
         if (state.socket && state.url === url && state.status === "open") {
            return
         }

         this._cleanup(key)

         state.url = url
         state.status = "connecting"

         const ws = new WebSocket(url, token)
         state.socket = ws

         ws.addEventListener("open", () => this._onOpen(key))
         ws.addEventListener("message", (e) => this._onMessage(key, e))
         ws.addEventListener("close", () => this._onClose(key))
         ws.addEventListener("error", () => this._onError(key))
      },

      disconnect(key) {
         const state = this.sockets[key]
         if (!state) return

         this._cleanup(key)
         delete this.sockets[key]
      },

      send(key, data) {
         const state = this.sockets[key]
         if (!state || !state.socket) return

         if (state.socket.readyState === WebSocket.OPEN) {
            state.socket.send(data)
         }
      },

      addListener(key, fn) {
         const state = this._ensure(key)
         state.listeners.add(fn)

         return () => state.listeners.delete(fn)
      },

      getStatus(key) {
         return this.sockets[key]?.status || "idle"
      },

      // ---------- INTERNAL ----------

      _ensure(key) {
         if (!this.sockets[key]) {
            this.sockets[key] = createState()
         }
         return this.sockets[key]
      },

      _cleanup(key) {
         const state = this.sockets[key]
         if (!state) return

         if (state.socket) {
            try { state.socket.close() } catch (_) {}
         }

         if (state.pingIntervalId) {
            clearInterval(state.pingIntervalId)
            state.pingIntervalId = null
         }

         if (state.reconnectTimer) {
            clearTimeout(state.reconnectTimer)
            state.reconnectTimer = null
         }

         state.socket = null
      },

      _onOpen(key) {
         const state = this.sockets[key]
         if (!state) return

         state.status = "open"
         state.lastPing = Date.now()
         state.reconnectAttempts = 0

         // heartbeat monitor
         state.pingIntervalId = setInterval(() => {
            const now = Date.now()

            if (now - state.lastPing > state.pingTimeout) {
               console.warn(`[WS:${key}] heartbeat timeout`)
               try { state.socket?.close() } catch (_) {}
            }
         }, 2500)
      },

      _onMessage(key, event) {
         const state = this.sockets[key]
         if (!state) return

         const data = event.data

         // heartbeat
         if (data === "PING") {
            state.lastPing = Date.now()
            this.send(key, "PONG")
            return
         }

         // dispatch to listeners
         for (const fn of state.listeners) {
            try {
               fn(data)
            } catch (e) {
               console.error(`[WS:${key}] listener failed`, e)
            }
         }
      },

      _onClose(key) {
         const state = this.sockets[key]
         if (!state) return

         state.status = "closed"

         this._scheduleReconnect(key)
      },

      _onError(key) {
         const state = this.sockets[key]
         if (!state) return

         state.status = "error"
      },

      _scheduleReconnect(key) {
         const state = this.sockets[key]
         if (!state || !state.url) return

         const delay = Math.min(1000 * 2 ** state.reconnectAttempts, 10000)
         state.reconnectAttempts++

         console.warn(`[WS:${key}] reconnect in ${delay}ms`)

         state.reconnectTimer = setTimeout(() => {
            this.connect(key, state.url)
         }, delay)
      }
   }
})