class RequestCancelledError extends Error {
   constructor(message) {
      super(message);
      this.name = "RequestCancelledError";
   }
}