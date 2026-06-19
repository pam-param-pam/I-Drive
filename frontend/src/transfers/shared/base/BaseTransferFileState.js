export class BaseTransferFileState {
   constructor(frontendId, fieldChangeCallback, { initialStatus, size, retryStatus, isErrorStatus }) {
      this.status = initialStatus
      this.error = null

      this.size = size
      this.progress = 0
      this.bytesTransferred = 0

      this._frontendId = frontendId
      this._fieldChangeCallback = fieldChangeCallback
      this._retryStatus = retryStatus
      this._isErrorStatus = isErrorStatus
   }

   emitInitialState() {
      for (const field of Object.keys(this)) {
         if (field.startsWith("_")) continue

         this._fieldChangeCallback?.({
            frontendId: this._frontendId,
            field,
            prev: undefined,
            current: this[field]
         })
      }
   }

   _set(field, value) {
      if (this[field] === value) return

      const prev = this[field]
      this[field] = value

      this._fieldChangeCallback?.({
         frontendId: this._frontendId,
         field,
         prev,
         current: value
      })
   }

   _increment(field, by = 1) {
      this._set(field, this[field] + by)
   }

   _mark(field) {
      this._set(field, true)
   }

   setStatus(status) {
      if (this.shouldBlockStatusOverride(status)) {
         console.warn("Possible override of error status!")
         console.warn(this.error)
         return
      }

      this._set("error", null)
      this._set("status", status)
   }

   shouldBlockStatusOverride(status) {
      return this.isErrorStatus() && status !== this._retryStatus
   }

   isErrorStatus() {
      return this._isErrorStatus(this.status)
   }

   setError(error) {
      this._set("error", error)
   }
   updateTransferredBytes(bytes) {
      let newBytes = this.bytesTransferred + bytes
      this._set("bytesTransferred", newBytes)
      this._updateByteProgress()
   }
   setTransferredBytes(bytes) {
      this._set("bytesTransferred", bytes)
      this._updateByteProgress()
   }

   _updateByteProgress() {
      const total = this.size
      const current = this.bytesTransferred
      const progress = Math.min(100, Math.floor((current / total) * 100))
      this._set("progress", progress)
   }
}