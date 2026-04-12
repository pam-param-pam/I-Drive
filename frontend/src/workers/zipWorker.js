import * as zip from "https://cdn.jsdelivr.net/npm/@zip.js/zip.js/+esm"

export function getFileType(fileName) {
   if (!fileName) return "Other"

   const idx = fileName.lastIndexOf(".")
   if (idx === -1) return "Other"

   const ext = fileName.slice(idx).toLowerCase()

   return extensionMap[ext] || "Other"
}

// ---- limits ----
const MAX_ENTRIES = 20_000

let zipTree = {}
let zipEntriesMap = {}

let baseUrl = null
let extensionMap = {}

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

function makeDownloadUrl(entry, url) {
   const params = new URLSearchParams({
      offset: entry.offset,
      compressed_size: entry.compressedSize,
      uncompressed_size: entry.uncompressedSize,
      compression_method: entry.compressionMethod,
      filename: entry.filename,
   })

   return url + "/zip-entry?" + params.toString()
}

function flatten(node, parentPath, url) {
   return Object.values(node).map(item => {
      const entry = item.entry

      return {
         id: item.path,
         name: item.name,
         isDir: item.isDir,
         type: getFileType(item.name),
         size: entry?.uncompressedSize || 0,
         parent_id: parentPath || null,
         rawEntry: entry,
         thumbOff: true,
         download_url: entry ? makeDownloadUrl(entry, url) : null
      }
   })
}

// --------------------
// SEARCH
// --------------------
function normalizeQuery(query) {
   return (query || "").toLowerCase().trim()
}

function searchEntries(query, url) {
   const q = normalizeQuery(query)

   if (!q) return []

   return Object.entries(zipEntriesMap)
      .filter(([path]) => path.toLowerCase().includes(q))
      .map(([path, entry]) => {
         const parts = path.split("/").filter(Boolean)
         const name = parts[parts.length - 1]
         const parentPath = parts.length > 1 ? parts.slice(0, -1).join("/") : null

         return {
            id: path,
            name,
            isDir: false,
            type: getFileType(name),
            size: entry?.uncompressedSize || 0,
            parent_id: parentPath,
            rawEntry: entry,
            thumbOff: true,
            download_url: makeDownloadUrl(entry, url)
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
         const { url, extensions } = payload

         baseUrl = url
         extensionMap = extensions || {}

         const reader = new zip.ZipReader(new zip.HttpReader(baseUrl, { useRangeHeader: true }))
         const generator = reader.getEntriesGenerator()

         const safeEntries = []

         for await (const entry of generator) {
            if (safeEntries.length >= MAX_ENTRIES) throw new Error("Zip archive has too many files")

            const u = safeNumber(entry.uncompressedSize)
            const c = Math.max(safeNumber(entry.compressedSize), 1)

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
         return
      }

      if (type === "list") {
         if (!baseUrl) throw new Error("Worker not initialized")

         const { path } = payload
         const node = resolveNode(path)
         const items = flatten(node, path, baseUrl)

         self.postMessage({ type: "list", items })
         return
      }

      if (type === "search") {
         if (!baseUrl) throw new Error("Worker not initialized")

         const { query } = payload
         const items = searchEntries(query, baseUrl)

         self.postMessage({ type: "search", items })
         return
      }

      throw new Error(`Unknown worker message type: ${type}`)
   } catch (err) {
      self.postMessage({ type: "error", error: err?.message || String(err) })
   }
}