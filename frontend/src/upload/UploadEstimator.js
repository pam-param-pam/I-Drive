export class UploadEstimator {
   constructor(windowMs = 5000) {
      this.windowMs = windowMs

      // Sliding window of byte deltas: [{ bytes, time }]
      this.samples = []
      this.smoothedEta = null
      this.etaSmoothing = 0.01 // α ∈ (0,1), lower = flatter

      this.previousRemainingBytes = null
   }

   _updateActualSpeed(remainingBytes) {
      const now = Date.now()

      if (this.previousRemainingBytes !== null) {
         const bytesDelta = this.previousRemainingBytes - remainingBytes
         if (bytesDelta > 0) {
            this.samples.push({ bytes: bytesDelta, time: now })
         }
      }

      this.previousRemainingBytes = remainingBytes

      // Drop samples outside sliding window
      const cutoff = now - this.windowMs
      while (this.samples.length && this.samples[0].time < cutoff) {
         this.samples.shift()
      }
   }

   getSpeed() {
      if (this.samples.length === 0) {
         return null
      }

      const now = Date.now()
      const oldest = this.samples[0].time
      const elapsedMs = Math.max(1, now - oldest)

      const totalBytes = this.samples.reduce((s, e) => s + e.bytes, 0)
      return totalBytes / (elapsedMs / 1000) // bytes/sec
   }

   estimateRemainingTime(remainingBytes) {
      this._updateActualSpeed(remainingBytes)

      const speed = this.getSpeed()
      if (!speed || speed <= 0) {
         return Infinity
      }

      const rawEta = Math.max(0, remainingBytes / speed)

      // First value: no smoothing yet
      if (this.smoothedEta === null || !isFinite(this.smoothedEta)) {
         this.smoothedEta = rawEta
         return rawEta
      }

      // Exponential moving average
      this.smoothedEta =
         this.smoothedEta +
         this.etaSmoothing * (rawEta - this.smoothedEta)

      return this.smoothedEta
   }
}
