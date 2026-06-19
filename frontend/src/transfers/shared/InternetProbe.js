import { checkWifi } from "@/api/user.js"

export class InternetProbe {
   constructor({ onRestored, intervalMs = 10000 }) {
      this.onRestored = onRestored
      this.intervalMs = intervalMs

      this._interval = null
      this._checking = false
   }

   start() {
      if (this._interval) return

      this._interval = setInterval(() => this._check(), this.intervalMs)
   }

   stop() {
      if (!this._interval) return

      clearInterval(this._interval)
      this._interval = null
   }

   async _check() {
      if (this._checking) return

      this._checking = true

      try {
         await checkWifi()
         this.stop()
         await this.onRestored()
      } catch {
      } finally {
         this._checking = false
      }
   }
}