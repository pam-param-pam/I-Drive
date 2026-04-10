import * as zip from "https://cdn.jsdelivr.net/npm/@zip.js/zip.js/+esm"

export function getFileType(fileName) {
  return  "Image"
}

// ---- limits ----
const MAX_ENTRIES = 20_000

let zipTree = {}
let zipEntriesMap = {}

function looksLikeArchive(name) {
   return /\.(zip|7z|rar|gz)$/i.test(name)
}

function safeNumber(v, d = 0) {
   return typeof v === "number" && isFinite(v) && v >= 0 ? v : d
}
// --------------------
// TREE BUILD
// --------------------
function buildTree(entries) {
   const root = {}
   const map = {}

   for (const entry of entries) {
      const path = entry.filename.replace(/\/$/, "")
      const parts = path.split("/").filter(Boolean)

      let current = root

      parts.forEach((part, index) => {
         const isLast = index === parts.length - 1

         if (!current[part]) {
            current[part] = {
               name: part,
               isDir: !isLast || entry.directory,
               children: {},
               path: parts.slice(0, index + 1).join("/"),
               entry: null
            }
         }

         if (isLast && !entry.directory) {
            current[part].entry = entry
            map[current[part].path] = entry
         }

         current = current[part].children
      })
   }

   return { root, map }
}

// --------------------
// NAV
// --------------------
function resolveNode(folderId) {
   if (!folderId) return zipTree

   const parts = folderId.split("/").filter(Boolean)
   let node = zipTree

   for (const part of parts) {
      node = node[part]?.children || {}
   }

   return node
}

function flatten(node, parentPath) {
   return Object.values(node).map(item => {
      const entry = item.entry

      let download = null
      if (entry) {
         const params = new URLSearchParams({
            offset: entry.offset,
            compressed_size: entry.compressedSize,
            uncompressed_size: entry.uncompressedSize,
            compression_method: entry.compressionMethod,
            filename: entry.filename
         })
         download = params.toString()
      }

      return {
         id: item.path,
         name: item.name,
         isDir: item.isDir,
         type: getFileType(item.name),
         // extension: detectExtension(item.name),
         size: entry?.uncompressedSize || 0,
         parent_id: parentPath || null,
         rawEntry: entry,
         download_query: download
      }
   })
}

// --------------------
// MAIN
// --------------------
self.onmessage = async (e) => {
   const { type, payload } = e.data

   try {
      if (type === "init") {
         const { url } = payload

         const reader = new zip.ZipReader(
            new zip.HttpReader(url, { useRangeHeader: true })
         )
         const entries = await reader.getEntries()

         if (entries.length > MAX_ENTRIES) throw new Error("Too many files")

         let total = 0
         const fileSize = reader.reader.size

         const safeEntries = []

         for (const entry of entries) {
            const u = safeNumber(entry.uncompressedSize)
            const c = Math.max(safeNumber(entry.compressedSize), 1)

            if (entry.offset < 0 || entry.offset > fileSize) {
               throw new Error("Invalid offset")
            }

            if (!entry.directory && looksLikeArchive(entry.filename)) {
               throw new Error("Nested archive")
            }

            safeEntries.push({
               filename: entry.filename,
               directory: entry.directory,
               compressionMethod: entry.compressionMethod,
               compressedSize: c,
               uncompressedSize: u,
               offset: entry.offset
            })
         }

         const built = buildTree(safeEntries)
         zipTree = built.root
         zipEntriesMap = built.map

         self.postMessage({ type: "ready" })
      }

      if (type === "list") {
         const { path } = payload

         const node = resolveNode(path)
         const items = flatten(node, path)

         self.postMessage({ type: "list", items })
      }

   } catch (err) {
      self.postMessage({ type: "error", error: err.message })
   }
}