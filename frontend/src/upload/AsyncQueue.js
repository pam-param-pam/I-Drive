export class AsyncQueue {
   constructor(maxSize = Infinity) {
      this.maxSize = maxSize

      this.queue = []
      this.waitingTakers = []
      this.waitingPutters = []

      this.closed = false
   }

   size() {
      return this.queue.length
   }

   isClosed() {
      return this.closed
   }

   async put(item) {
      if (this.closed) {
         throw new Error("AsyncQueue is closed")
      }

      // If someone is waiting to take, resolve immediately
      if (this.waitingTakers.length > 0) {
         const taker = this.waitingTakers.shift()
         taker.resolve(item)
         return
      }

      // If queue has space, enqueue
      if (this.queue.length < this.maxSize) {
         this.queue.push(item)
         return
      }

      // Otherwise wait (backpressure)
      return new Promise((resolve, reject) => {
         this.waitingPutters.push({ item, resolve, reject })
      })
   }

   async take() {
      // If queue has data, return immediately
      if (this.queue.length > 0) {
         const item = this.queue.shift()

         // If someone was blocked on put(), let one in
         if (this.waitingPutters.length > 0) {
            const putter = this.waitingPutters.shift()
            this.queue.push(putter.item)
            putter.resolve()
         }

         return item
      }

      // If closed and empty → end of stream
      if (this.closed) {
         return null
      }

      // Otherwise wait
      return new Promise((resolve, reject) => {
         this.waitingTakers.push({ resolve, reject })
      })
   }

   close() {
      console.log("closing loop")
      if (this.closed) return
      this.closed = true

      // Wake all takers with null
      for (const taker of this.waitingTakers) {
         taker.resolve(null)
      }
      this.waitingTakers.length = 0

      // Reject all blocked putters
      for (const putter of this.waitingPutters) {
         putter.reject(new Error("AsyncQueue closed"))
      }
      this.waitingPutters.length = 0
   }

   open() {
      this.closed = false
   }

   clear() {
      this.queue.length = 0
   }
}
