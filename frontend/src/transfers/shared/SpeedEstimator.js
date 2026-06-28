export class SpeedEstimator {
   constructor(windowMs = 5000) {
      this.windowMs = windowMs

      // Sliding window of byte deltas: [{ bytes, time }]
      this.samples = []

      this.etaSmoothing = 0.01 // α ∈ (0,1), lower = flatter
      this.firstSpikeThreshold = 500

      this.previousRemainingBytes = null

      this.currentSpeed = null
      this.currentEta = Infinity
      this.smoothedEta = null
   }

   update(remainingBytes) {
      if (remainingBytes === undefined || isNaN(remainingBytes)) {
         console.warn("[Estimator] remainingBytes is undefined or NaN")
         this.currentSpeed = null
         this.currentEta = Infinity
         return
      }

      const now = Date.now()

      if (this.previousRemainingBytes !== null) {
         const bytesDelta = this.previousRemainingBytes - remainingBytes

         if (bytesDelta > 0) {
            this.samples.push({ bytes: bytesDelta, time: now })
         }
      }

      this.previousRemainingBytes = remainingBytes

      this._dropOldSamples(now)

      this.currentSpeed = this._calculateSpeed(now)
      this.currentEta = this._calculateEta(remainingBytes)
   }

   getSpeed() {
      return this.currentSpeed
   }

   getEta() {
      return this.currentEta
   }

   _dropOldSamples(now) {
      const cutoff = now - this.windowMs

      while (this.samples.length && this.samples[0].time < cutoff) {
         this.samples.shift()
      }
   }

   _calculateSpeed(now) {
      if (this.samples.length === 0) return null

      const oldest = this.samples[0].time
      const elapsedMs = now - oldest

      if (elapsedMs < this.firstSpikeThreshold) {
         return null
      }

      const totalBytes = this.samples.reduce((sum, sample) => sum + sample.bytes, 0)

      return totalBytes / (elapsedMs / 1000)
   }

   _calculateEta(remainingBytes) {
      const speed = this.currentSpeed

      if (!speed || speed <= 0) {
         return Infinity
      }

      const rawEta = Math.max(0, remainingBytes / speed)

      if (this.smoothedEta === null || !isFinite(this.smoothedEta)) {
         this.smoothedEta = rawEta
         return rawEta
      }

      this.smoothedEta = this.smoothedEta + this.etaSmoothing * (rawEta - this.smoothedEta)

      return this.smoothedEta
   }
}