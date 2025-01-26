export function isMobile() {
   return window.innerWidth <= 950
}

export function formatSeconds(seconds) {
   let h = Math.floor(seconds / 3600)
   let m = Math.floor((seconds % 3600) / 60)
   let s = Math.round(seconds % 60)
   let t = [h, m > 9 ? m : h ? '0' + m : m || '0', s > 9 ? s : '0' + s]
      .filter(Boolean)
      .join(':')
   return seconds < 0 && seconds ? `-${t}` : t
}

export function detectExtension(filename) {
   let arry = filename.split(".")

   if (arry.length === 1) return ".txt" //missing extension defaults to .txt
   return "." + arry[arry.length - 1]

}
