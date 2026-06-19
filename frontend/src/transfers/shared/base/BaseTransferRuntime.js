import { SpeedEstimator } from "@/transfers/shared/SpeedEstimator.js"

export class BaseTransferRuntime {
   constructor({ initialState, runningState, finishCallback}) {
      this.fileStates = new Map()
      this.estimator = new SpeedEstimator()

      this.allBytesTransfered = 0
      this.allBytesToTransfer = 0


      this.transferState = initialState

      this._initialState = initialState
      this._runningState = runningState
      this._finishCallback = finishCallback

      this._globalStateListeners = new Set()
      this._transferStateListeners = new Set()
      this._fileFinishedListeners = new Set()
      this._fileChangeSubscriptions = new Set()
   }

   toGlobalSnapshot() {
      throw new Error(`${this.constructor.name}.toGlobalSnapshot() must be implemented`)
   }

   getRemainingBytes() {
      return Math.max(0, this.allBytesToTransfer - this.allBytesTransfered)
   }

   onFileChange(fields, listener) {
      if (!Array.isArray(fields) || fields.length === 0) {
         throw new Error("onFileChange requires a non-empty field list")
      }

      const sub = { fields: new Set(fields), listener }
      this._fileChangeSubscriptions.add(sub)

      return () => this._fileChangeSubscriptions.delete(sub)
   }

   onGlobalStateChange(listener) {
      this._globalStateListeners.add(listener)
      return () => this._globalStateListeners.delete(listener)
   }

   onTransferStateChange(listener) {
      this._transferStateListeners.add(listener)
      return () => this._transferStateListeners.delete(listener)
   }

   updateAllBytesToTransfer(bytes) {
      this.allBytesToTransfer = bytes
      this._emitGlobalState()
   }

   onFileFinished(listener) {
      this._fileFinishedListeners.add(listener)
      return () => this._fileFinishedListeners.delete(listener)
   }

   getFileState(id) {
      const state = this.fileStates.get(id)

      if (!state) {
         console.warn(`${this.constructor.name}: couldn't find file state for: ${id}`)
      }
      return state
   }

   setTransferState(state) {
      if (this.transferState === state) return

      this.transferState = state
      this._emitTransferState(state)
      this._emitGlobalState()
   }

   async waitUntilResumed(signal = null) {
      if (this.transferState === this._runningState) return
      if (signal?.aborted) return

      return new Promise(resolve => {
         let unsubscribe = null

         const cleanup = () => {
            if (unsubscribe) {
               unsubscribe()
               unsubscribe = null
            }

            signal?.removeEventListener("abort", onAbort)
         }

         const finish = () => {
            cleanup()
            resolve()
         }

         const onAbort = () => {
            finish()
         }

         unsubscribe = this.onTransferStateChange(newState => {
            if (newState === this._runningState) {
               finish()
            }
         })

         signal?.addEventListener("abort", onAbort, { once: true })
      })
   }

   isTransferFullyFinished() {
      return this.fileStates.size === 0
   }

   cleanup() {
      this.fileStates.clear()
      this._globalStateListeners.clear()
      this._transferStateListeners.clear()
      this._fileFinishedListeners.clear()
      this._fileChangeSubscriptions.clear()

      this.transferState = this._initialState
   }

   _onRawFileFieldChange(change) {
      const { frontendId, field } = change

      for (const sub of this._fileChangeSubscriptions) {
         if (sub.fields.has(field)) {
            sub.listener({
               frontendId,
               field,
               prev: change.prev,
               current: change.current
            })
         }
      }
   }

   _emitGlobalState() {
      const snapshot = this.toGlobalSnapshot()

      for (const listener of this._globalStateListeners) {
         listener(snapshot)
      }
   }

   _emitTransferState(state) {
      for (const listener of this._transferStateListeners) {
         listener(state)
      }
   }

   _emitFileFinished(id) {
      for (const listener of this._fileFinishedListeners) {
         listener(id)
      }
   }

   _finishExistingFile(id) {
      this.fileStates.delete(id)
      this._emitFileFinished(id)
      this._emitGlobalState()
      this._checkAllFilesFinished()
   }

   _checkAllFilesFinished() {
      if (this.isTransferFullyFinished() && this._finishCallback) {
         this._finishCallback()
      }
   }
}