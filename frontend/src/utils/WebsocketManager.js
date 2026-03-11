import { showToast } from "@/utils/common.js"

export class WebSocketManager {

   constructor(socketGetter, onEvent) {
      this.getSocket = socketGetter
      this.onEvent = onEvent

      this.socket = null

      this.lastPing = Date.now()
      this.PING_TIMEOUT = 150000
      this.CHECK_INTERVAL = 2500

      this.monitor = null

      this.handleMessage = this.handleMessage.bind(this)
      this.handleError = this.handleError.bind(this)
      this.handleOpen = this.handleOpen.bind(this)
      this.handleClose = this.handleClose.bind(this)

      this.attachSocket()
      this.startMonitor()
      this.startSocketWatcher()
   }

   attachSocket() {
      const newSocket = this.getSocket()

      if (!newSocket || newSocket === this.socket) return

      if (this.socket) this.unbind()

      this.socket = newSocket
      this.bind()
   }

   bind() {
      this.socket.addEventListener("message", this.handleMessage)
      this.socket.addEventListener("error", this.handleError)
      this.socket.addEventListener("open", this.handleOpen)
      this.socket.addEventListener("close", this.handleClose)
   }

   unbind() {
      this.socket.removeEventListener("message", this.handleMessage)
      this.socket.removeEventListener("error", this.handleError)
      this.socket.removeEventListener("open", this.handleOpen)
      this.socket.removeEventListener("close", this.handleClose)
   }

   startSocketWatcher() {
      setInterval(() => {
         const current = this.getSocket()
         if (current && current !== this.socket) {
            console.warn("WebSocket instance replaced, rebinding")
            this.attachSocket()
         }
      }, 1000)
   }

   handleOpen() {
      this.lastPing = Date.now()
   }

   handleClose() {
      console.warn("WebSocket closed")
   }

   handleError() {
      showToast("error", "toasts.failedToConnectToWebsocket")
   }

   async handleMessage(message) {
      if (this.handleHeartbeat(message)) return

      try {
         await this.onEvent(message)
      } catch (e) {
         console.error("WebSocket event handler failed", e)
      }
   }

   handleHeartbeat(message) {
      try {
         if (message.data === "PING") {
            this.lastPing = Date.now()
            this.send("PONG")
            return true
         }
      } catch (_) {
      }

      return false
   }

   startMonitor() {
      if (this.monitor) return

      this.monitor = setInterval(() => {

         const now = Date.now()

         if (now - this.lastPing > this.PING_TIMEOUT) {

            console.warn("WebSocket heartbeat timeout")

            try {
               if (this.socket) this.socket.close()
            } catch (_) {
            }

            this.lastPing = now
         }

      }, this.CHECK_INTERVAL)
   }

   send(text) {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
         this.socket.send(text)
      }
   }
}
