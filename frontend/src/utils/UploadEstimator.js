export class UploadEstimator {
   constructor(smoothingFactor = 0.1, trendWeight = 0.2, windowSize = 20000, feedbackFactor = 0.05) {
      this.windowSize = windowSize
      this.feedbackFactor = feedbackFactor  // Controls how much past error influences the next estimate
      this.buffer = []                       // Stores recent speeds with timestamps
      this.previousEstimate = null           // Holds the previous estimate for error calculation
      this.previousRemainingBytes = null     // Holds the previous bytes for error calculation
   }

   updateSpeed(currentSpeed) {
      const currentTime = Date.now() // Capture the current timestamp in milliseconds

      // Add new speed with timestamp to the buffer
      this.buffer.push({ currentSpeed, currentTime })

      // Remove data older than the defined window size
      this.buffer = this.buffer.filter(entry =>
         (currentTime - entry.currentTime) <= this.windowSize
      )
   }

   calculateAverageSpeed() {
      // Return 0 if there's no data in the last 30 seconds
      if (this.buffer.length === 0) return 0

      // Sum up the speeds in the buffer
      const speedSum = this.buffer.reduce((sum, entry) => sum + entry.currentSpeed, 0)

      // Calculate the average speed
      return speedSum / this.buffer.length
   }

   estimateRemainingTime(remainingBytes) {
      // Calculate the average speed over the last windowSize
      let averageSpeed = this.calculateAverageSpeed()

      // If no valid speed data or if speed is zero, return 0
      if (averageSpeed <= 0) return 0

      // Calculate estimated time remaining based on average speed
      let estimatedTime = remainingBytes / averageSpeed

      // Adjust based on previous estimate error
      if (this.previousEstimate !== null && this.previousRemainingBytes !== null) {
         const actualBytesTransferred = this.previousRemainingBytes - remainingBytes
         const actualTimeElapsed = actualBytesTransferred / averageSpeed

         // Calculate the error as the difference between estimated and actual time
         const error = actualTimeElapsed - this.previousEstimate

         // Adjust current estimate based on feedback from previous error
         estimatedTime -= error * this.feedbackFactor
      }

      // Update previous estimate and remaining bytes for the next iteration
      this.previousEstimate = estimatedTime
      this.previousRemainingBytes = remainingBytes

      return estimatedTime
   }
}
