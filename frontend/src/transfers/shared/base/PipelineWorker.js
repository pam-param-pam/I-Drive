import { workerExitReason } from "@/transfers/shared/constants.js"


export class PipelineWorker {
   constructor() {
      this._running = false
      this._stopRequested = false
      this._killed = false

      this._abortController = null
      this._stopController = null

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
      this._stopController = new AbortController()

      this._exitPromise = new Promise(resolve => {
         this._resolveExit = resolve
      })

      return this._abortController.signal
   }

   _markFinished(exitReason) {
      const workerName = this.name()
      console.debug(`${workerName} finished (${exitReason})`)

      this._running = false
      this._abortController = null
      this._stopController = null

      this._resolveExit?.(exitReason)
      this._resolveExit = null
      this._exitPromise = null
   }

   _handleRunError(err) {
      const workerName = this.name()

      if (this.isAbortError(err) || this.isQueueClosedError(err)) {
         return this._killed ? workerExitReason.killed : workerExitReason.stopped
      }

      console.error(`${workerName} crashed:`, err)
      throw err
   }

   _throwIfAborted(signal) {
      if (signal?.aborted) {
         throw new DOMException("Aborted", "AbortError")
      }
   }

   takeWithAbort(queue, signal) {
      return new Promise((resolve, reject) => {
         if (signal?.aborted || this._stopController?.signal.aborted) {
            reject(new DOMException("Aborted", "AbortError"))
            return
         }

         const abortHandler = () => {
            cleanup()
            reject(new DOMException("Aborted", "AbortError"))
         }

         const stopHandler = () => {
            cleanup()
            reject(new DOMException("Stopped", "AbortError"))
         }

         const cleanup = () => {
            signal?.removeEventListener("abort", abortHandler)
            this._stopController?.signal.removeEventListener("abort", stopHandler)
         }

         signal?.addEventListener("abort", abortHandler, { once: true })
         this._stopController?.signal.addEventListener("abort", stopHandler, { once: true })

         queue.take()
            .then(item => {
               cleanup()
               resolve(item)
            })
            .catch(err => {
               cleanup()
               reject(err)
            })
      })
   }

   putWithAbort(queue, item, signal, options = {}) {
      return new Promise((resolve, reject) => {
         if (signal?.aborted) {
            reject(new DOMException("Aborted", "AbortError"))
            return
         }

         const abortHandler = () => {
            cleanup()
            reject(new DOMException("Aborted", "AbortError"))
         }

         const cleanup = () => {
            signal?.removeEventListener("abort", abortHandler)
         }

         signal?.addEventListener("abort", abortHandler, { once: true })

         queue.put(item, options)
            .then(() => {
               cleanup()
               resolve()
            })
            .catch(err => {
               cleanup()
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
      this._stopController?.abort()

      if (!this._running) {
         return workerExitReason.stopped
      }

      return this._exitPromise
   }

   async kill() {
      this._stopRequested = true
      this._killed = true

      this._stopController?.abort()
      this._abortController?.abort()

      if (!this._running) {
         return workerExitReason.killed
      }

      return this._exitPromise
   }
}