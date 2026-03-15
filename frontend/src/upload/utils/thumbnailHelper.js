import jsmediatags from "jsmediatags"

function isBadFrame(ctx, width, height) {
   try {
      const sample = 20
      const data = ctx.getImageData(
         Math.floor(width / 2 - sample / 2),
         Math.floor(height / 2 - sample / 2),
         sample,
         sample
      ).data

      let brightness = 0
      let alpha = 0
      const pixels = data.length / 4

      for (let i = 0; i < data.length; i += 4) {
         brightness += data[i] + data[i + 1] + data[i + 2]
         alpha += data[i + 3]
      }

      const avgBrightness = brightness / (pixels * 3)
      const avgAlpha = alpha / pixels

      if (avgAlpha < 5) return true
      return avgBrightness < 10;


   } catch {
      return false
   }
}

function setupVideo(file) {
   const video = document.createElement("video")
   const url = URL.createObjectURL(file)

   video.src = url
   video.muted = true
   video.crossOrigin = "anonymous"
   video.preload = "metadata"
   video.load()

   return { video, url }
}

export async function fastVideoThumbnail(
   file,
   seekTo = -2,
   maxWidth = 1920,
   maxHeight = 1080,
   quality = 0.5
) {
   const { video, url } = setupVideo(file)

   let waitingForSeek = false
   let targetTime = 0
   let resolved = false
   let attempt = 0
   let duration = 0

   const MAX_ATTEMPTS = 5

   const candidates = [
      d => d + 2,
      d => d + 4,
      d => d * 0.2,
      d => d * 0.3,
      d => d * 0.5
   ]

   return new Promise((resolve, reject) => {

      const cleanup = () => {
         document.removeEventListener("visibilitychange", onVisibilityChange)
         video.onerror = null
         video.onloadedmetadata = null
         video.onseeked = null
         URL.revokeObjectURL(url)
         video.src = ""
      }

      const onVisibilityChange = () => {
         if (!document.hidden && waitingForSeek) {
            try { video.currentTime = targetTime } catch {}
         }
      }

      function nextSeekTime() {
         attempt++
         if (attempt >= MAX_ATTEMPTS) return null
         const candidate = candidates[attempt](duration)
         return Math.max(0, Math.min(candidate, Math.max(0, duration - 0.1)))
      }

      video.onerror = () => {
         if (resolved) return
         resolved = true
         cleanup()
         reject(new Error("Failed to load video"))
      }

      video.onloadedmetadata = () => {
         duration = video.duration || 0
         targetTime = Math.max(0, Math.min(seekTo, Math.max(0, duration - 0.1)))
         waitingForSeek = true
         video.currentTime = targetTime
      }

      video.onseeked = async () => {
         if (!waitingForSeek || resolved) return
         waitingForSeek = false

         let canvas, ctx
         try {
            canvas = document.createElement("canvas")
            ctx = canvas.getContext("2d")
            if (!ctx) throw new Error("Canvas context not available")

            canvas.width = video.videoWidth
            canvas.height = video.videoHeight
            ctx.drawImage(video, 0, 0)
         } catch (e) {
            resolved = true
            cleanup()
            reject(e)
            return
         }

         if (isBadFrame(ctx, canvas.width, canvas.height)) {
            const next = nextSeekTime()
            if (next !== null) {
               waitingForSeek = true
               targetTime = next
               try { video.currentTime = targetTime } catch {}
               return
            }
         }

         try {
            const blob = await resizeAndEncode(video, {
               maxWidth,
               maxHeight,
               quality
            })

            resolved = true
            cleanup()
            resolve(blob)

         } catch (err) {
            resolved = true
            cleanup()
            reject(err)
         }
      }

      document.addEventListener("visibilitychange", onVisibilityChange)
   })
}

export async function slowVideoCover(
   file,
   maxWidth = 1920,
   maxHeight = 1080,
   quality = 0.75
) {
   const { video, url } = setupVideo(file)

   let waitingForSeek = false
   let targetTime = 0
   let resolved = false
   let duration = 0
   let index = 0

   const blobs = []
   const intervals = [0.1, 0.2, 0.3, 0.4, 0.5]

   return new Promise((resolve, reject) => {

      const cleanup = () => {
         document.removeEventListener("visibilitychange", onVisibilityChange)
         video.onerror = null
         video.onloadedmetadata = null
         video.onseeked = null
         URL.revokeObjectURL(url)
         video.src = ""
      }

      const onVisibilityChange = () => {
         if (!document.hidden && waitingForSeek) {
            try { video.currentTime = targetTime } catch {}
         }
      }

      function seekNext() {
         if (index >= intervals.length) return finish()

         targetTime = Math.max(
            0,
            Math.min(duration * intervals[index], Math.max(0, duration - 0.1))
         )

         index++
         waitingForSeek = true

         try { video.currentTime = targetTime } catch {}
      }

      function finish() {
         if (resolved) return
         resolved = true
         cleanup()

         if (!blobs.length) {
            reject(new Error("No valid thumbnails generated"))
            return
         }

         let best = blobs[0]
         for (const b of blobs) {
            if (b.size > best.size) best = b
         }

         resolve(best)
      }

      video.onerror = () => {
         if (resolved) return
         resolved = true
         cleanup()
         reject(new Error("Failed to load video"))
      }

      video.onloadedmetadata = () => {
         duration = video.duration || 0
         seekNext()
      }

      video.onseeked = async () => {
         if (!waitingForSeek || resolved) return
         waitingForSeek = false

         let canvas, ctx
         try {
            canvas = document.createElement("canvas")
            ctx = canvas.getContext("2d")
            if (!ctx) throw new Error("Canvas context not available")

            canvas.width = video.videoWidth
            canvas.height = video.videoHeight
            ctx.drawImage(video, 0, 0)
         } catch (e) {
            resolved = true
            cleanup()
            reject(e)
            return
         }

         if (!isBadFrame(ctx, canvas.width, canvas.height)) {
            try {
               const blob = await resizeAndEncode(video, {
                  maxWidth,
                  maxHeight,
                  quality
               })

               blobs.push(blob)
            } catch {}
         }

         seekNext()
      }

      document.addEventListener("visibilitychange", onVisibilityChange)
   })
}

export function generateRawImageThumbnail(file, options = {}) {
   return new Promise((resolve, reject) => {
      const reader = new FileReader()

      reader.onerror = () => reject(reader.error)

      reader.onload = async (e) => {
         try {
            const buf = new Uint8Array(e.target.result)

            const metadata = dcraw(buf, { verbose: true, identify: true })
            const thumbnailBytes = dcraw(buf, { extractThumbnail: true })

            const originalBlob = new Blob([thumbnailBytes])

            const bitmap = await createImageBitmap(originalBlob)
            const webpBlob = await resizeAndEncode(bitmap, options)
            bitmap.close()

            resolve({
               thumbnail: webpBlob,
               metadata
            })
         } catch (err) {
            reject(err)
         }
      }

      reader.readAsArrayBuffer(file)
   })
}

export async function generateAudioThumbnail(file, options = {}) {
   return new Promise((resolve, reject) => {
      jsmediatags.read(file, {
         onSuccess: async (tag) => {
            try {
               const picture = tag.tags.picture
               if (!picture) throw new Error("No picture found in audio file")

               const { data, format } = picture
               const byteArray = new Uint8Array(data)
               const blob = new Blob([byteArray], { type: format })

               const img = new Image()

               img.onload = async () => {
                  try {
                     const webpBlob = await resizeAndEncode(img, options)
                     URL.revokeObjectURL(img.src)
                     resolve(webpBlob)
                  } catch (err) {
                     URL.revokeObjectURL(img.src)
                     reject(err)
                  }
               }

               img.onerror = () => {
                  URL.revokeObjectURL(img.src)
                  reject(new Error("Failed to decode audio cover"))
               }
               img.src = URL.createObjectURL(blob)
            } catch (err) {
               reject(err)
            }
         },
         onError: (error) => {
            console.error("Error reading file:", error.type, error.info)
            reject(new Error("Failed to read audio file"))
         }
      })
   })
}

export async function generateImageThumbnail(file, options = {}) {
   return new Promise((resolve, reject) => {

      const url = URL.createObjectURL(file)
      const img = new Image()

      img.onload = async () => {
         try {
            const blob = await resizeAndEncode(img, options)

            URL.revokeObjectURL(url)

            resolve({
               thumbnail: blob,
               photoMetadata: {
                  width: img.naturalWidth || img.width,
                  height: img.naturalHeight || img.height
               }
            })

         } catch (err) {
            URL.revokeObjectURL(url)
            reject(err)
         }
      }

      img.onerror = () => {
         URL.revokeObjectURL(url)
         reject(new Error("Failed to decode image"))
      }

      img.src = url
   })
}

export async function resizeAndEncode(source, options = {}) {
   const {
      quality = 0.75,
      maxWidth = 1920,
      maxHeight = 1080,
      format = "image/webp"
   } = options

   let width = source.videoWidth || source.width
   let height = source.videoHeight || source.height

   if (width > height) {
      if (width > maxWidth) {
         height *= maxWidth / width
         width = maxWidth
      }
   } else {
      if (height > maxHeight) {
         width *= maxHeight / height
         height = maxHeight
      }
   }

   const canvas = document.createElement("canvas")
   const ctx = canvas.getContext("2d")

   if (!ctx) throw new Error("Canvas context not available")

   canvas.width = Math.round(width)
   canvas.height = Math.round(height)

   ctx.drawImage(source, 0, 0, canvas.width, canvas.height)

   const blob = await new Promise(resolve =>
      canvas.toBlob(resolve, format, quality)
   )

   if (!blob) throw new Error("Failed to encode image")

   return blob
}


export async function getMomentFrame(video, options = {}) {
   const {
      quality = 0.5,
      maxWidth = 720,
      maxHeight = 480,
      format = "image/webp"
   } = options

   const canvas = document.createElement("canvas")
   const ctx = canvas.getContext("2d")

   if (!ctx) throw new Error("Canvas context not available")

   canvas.width = video.videoWidth
   canvas.height = video.videoHeight

   ctx.drawImage(video, 0, 0)

   return await resizeAndEncode(canvas, {
      quality,
      maxWidth,
      maxHeight,
      format
   })
}
