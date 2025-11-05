function parseStylAtom(data, offset = 0) {
   const dv = new DataView(data.buffer, data.byteOffset + offset)
   const size = dv.getUint32(0)
   const type = new TextDecoder().decode(data.slice(offset + 4, offset + 8))
   if (type !== "styl") return null

   const entryCount = dv.getUint16(8)
   const entries = []
   let pos = 10
   for (let i = 0; i < entryCount; i++) {
      const startChar = dv.getUint16(pos)
      pos += 2
      const endChar = dv.getUint16(pos)
      pos += 2
      const fontID = dv.getUint16(pos)
      pos += 2
      const faceStyleFlags = dv.getUint8(pos++)
      const fontSize = dv.getUint8(pos++)
      const color = [
         dv.getUint8(pos++),
         dv.getUint8(pos++),
         dv.getUint8(pos++),
         dv.getUint8(pos++)
      ]
      entries.push({ startChar, endChar, fontID, faceStyleFlags, fontSize, color })
   }
   return { size, type, entryCount, entries }
}


function stylToVtt(text, styl) {
   if (!styl || styl.entryCount === 0) return text

   const entry = styl.entries[0]
   const { startChar, endChar, faceStyleFlags, color } = entry

   let styled = text.slice(startChar, endChar)

   // Apply color
   const hexColor = `#${color.slice(0, 3).map(x => x.toString(16).padStart(2, "0")).join("")}`
   styled = `<font color="${hexColor}">${styled}</font>`

   // Apply bold / italic / underline
   if (faceStyleFlags & 0x04) styled = `<u>${styled}</u>`
   if (faceStyleFlags & 0x02) styled = `<i>${styled}</i>`
   if (faceStyleFlags & 0x01) styled = `<b>${styled}</b>`

   // Recombine with unstyled text
   return text.slice(0, startChar) + styled + text.slice(endChar)
}


function decodeTx3gToVtt(data) {
   const dv = new DataView(data.buffer, data.byteOffset, data.byteLength)
   const textLen = dv.getUint16(0, false) // BE
   const textStart = 2
   const textEnd = Math.min(textStart + textLen, dv.byteLength)

   if (textLen === 0) return
   const textPreview = new TextDecoder().decode(data.slice(2, Math.min(textEnd, 64)))

   if (textEnd + 22 === data.length) {
      const styl = parseStylAtom(data, textEnd)
      return stylToVtt(textPreview, styl)
   }
   return textPreview
}


function formatVttTime(sec) {
   const h = Math.floor(sec / 3600)
   const m = Math.floor((sec % 3600) / 60)
   const s = (sec % 60).toFixed(3)
   return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(6, "0")}`
}


export function buildVttFromSamples(subTrack, samples) {
   const lines = []
   lines.push("WEBVTT")
   let idx = 1
   for (const s of samples) {
      const start = s.dts / subTrack.timescale
      const end = (s.dts + s.duration) / subTrack.timescale
      const text = decodeTx3gToVtt(s.data)

      if (!text) continue
      lines.push(`${idx++}`)
      lines.push(`${formatVttTime(start)} --> ${formatVttTime(end)}`)
      lines.push(text)
      lines.push("")
   }
   return new Blob([lines.join("\n")], { type: "text/plain" })
}

export function buildVttFromSrt(srtText) {
   let vtt = srtText.replace(/\r+/g, "").trim()

   vtt = vtt.replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2")

   vtt = "WEBVTT\n\n" + vtt

   return new Blob([vtt], { type: "text/plain" })
}