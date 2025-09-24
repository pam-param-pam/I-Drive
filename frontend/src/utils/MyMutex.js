export class MyMutex {
   constructor() {
      this._locked = false
      this._waiters = []
   }

   async lock() {
      if (!this._locked) {
         this._locked = true
         return () => this.unlock() // return unlock function
      }
      return new Promise(resolve => {
         this._waiters.push(() => {
            this._locked = true
            resolve(() => this.unlock())
         })
      })
   }

   unlock() {
      if (this._waiters.length > 0) {
         const next = this._waiters.shift()
         next()
      } else {
         this._locked = false
      }
   }
}
