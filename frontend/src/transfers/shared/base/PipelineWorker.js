import { workerExitReason } from "@/transfers/shared/constants.js"

export class PipelineWorker {
   constructor() {
      this._running = false
      this._stopRequested = false
      this._killed = false
      this._abortController = null

      this._exitPromise = null
      this._resolveExit = null
      console.info(`Creating ${this.name()}!`)
   }
   name() {
      return this.constructor.name
   }

   isRunning() {
      return this._running
   }

   _markStarted() {
      if (this._running) {
         throw new Error("Worker is already running")
      }

      this._running = true
      this._stopRequested = false
      this._killed = false
      this._abortController = new AbortController()

      this._exitPromise = new Promise(resolve => {
         this._resolveExit = resolve
      })

      return this._abortController.signal
   }

   _markFinished(exitReason) {
      let workerName = this.name()
      console.debug(`${workerName} finished (${exitReason})`)

      this._running = false
      this._abortController = null

      this._resolveExit?.(exitReason)
      this._resolveExit = null
      this._exitPromise = null
   }

   _handleRunError(err) {
      let workerName = this.name()
      if (this.isAbortError(err) || this.isQueueClosedError(err)) {
         return this._killed ? workerExitReason.killed : workerExitReason.stopped
      }

      console.error(`${workerName} crashed:`, err)
      throw err
   }
   _throwIfAborted(signal) {
      if (signal.aborted) {
         throw new DOMException("Aborted", "AbortError")
      }
   }

   takeWithAbort(queue, signal) {
      return new Promise((resolve, reject) => {
         if (signal?.aborted) {
            reject(new DOMException("Aborted", "AbortError"))
            return
         }

         const abortHandler = () => {
            reject(new DOMException("Aborted", "AbortError"))
         }

         signal?.addEventListener("abort", abortHandler, { once: true })

         queue
            .take()
            .then(item => {
               signal?.removeEventListener("abort", abortHandler)
               resolve(item)
            })
            .catch(err => {
               signal?.removeEventListener("abort", abortHandler)
               reject(err)
            })
      })
   }

   putWithAbort(queue, item, signal, force=false) {
      return new Promise((resolve, reject) => {
         if (signal?.aborted) {
            reject(new DOMException("Aborted", "AbortError"))
            return
         }

         const abortHandler = () => {
            reject(new DOMException("Aborted", "AbortError"))
         }

         signal?.addEventListener("abort", abortHandler, { once: true })

         queue
            .put(item, force)
            .then(() => {
               signal?.removeEventListener("abort", abortHandler)
               resolve()
            })
            .catch(err => {
               signal?.removeEventListener("abort", abortHandler)
               reject(err)
            })
      })
   }

   isAbortError(err) {
      return err?.name === "AbortError" || err?.code === "ABORT_ERR"
   }

   isQueueClosedError(err) {
      return err?.message === "AsyncQueue closed"
   }

   async stop() {
      this._stopRequested = true

      if (!this._running) {
         return workerExitReason.stopped
      }

      return this._exitPromise
   }

   async kill() {
      this._stopRequested = true
      this._killed = true
      this._abortController?.abort()

      if (!this._running) {
         return workerExitReason.killed
      }

      return this._exitPromise
   }
}