import * as zip from "https://cdn.jsdelivr.net/npm/@zip.js/zip.js/+esm"
import { detectExtension } from "@/utils/common.js"

export function getFileType(fileName) {
   if (!fileName) return "Other"
   const idx = fileName.lastIndexOf(".")
   if (idx === -1) return "Other"
   return extensionMap[fileName.slice(idx).toLowerCase()] || "Other"
}

const MAX_ENTRIES = 20_000

let zipTree = {}
let zipEntriesMap = {}
let zipPathById = {}
let zipIdByPath = {}
let baseUrl = null
let extensionMap = {}

function safeNumber(v, d = 0) {
   return typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : d
}

async function hashPath(path) {
   const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(path))
   return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("")
}

async function getOrCreatePathId(path, pathById, idByPath) {
   if (idByPath[path]) return idByPath[path]

   const fileId = await hashPath(path)
   if (pathById[fileId] && pathById[fileId] !== path) throw new Error(`Path hash collision between "${pathById[fileId]}" and "${path}"`)

   pathById[fileId] = path
   idByPath[path] = fileId
   return fileId
}

async function buildTree(entries) {
   const root = {}
   const map = {}
   const pathById = {}
   const idByPath = {}

   for (const entry of entries) {
      const rawPath = entry.raw_path
      const parts = rawPath.split("/").filter(Boolean)
      let current = root

      for (let index = 0; index < parts.length; index++) {
         const name = parts[index]
         const isLast = index === parts.length - 1
         const itemPath = parts.slice(0, index + 1).join("/")

         if (!current[name]) {
            current[name] = {
               fileId: await getOrCreatePathId(itemPath, pathById, idByPath),
               raw_path: itemPath,
               name,
               isDir: !isLast || Boolean(entry.directory),
               children: {},
               entry: null
            }
         }

         if (isLast) {
            current[name].isDir = Boolean(entry.directory)

            if (!entry.directory) {
               current[name].entry = entry
               map[itemPath] = entry
            }
         }

         current = current[name].children
      }
   }

   return { root, map, pathById, idByPath }
}

function resolveNode(folderId) {
   if (!folderId) return zipTree

   const rawPath = zipPathById[folderId]
   if (!rawPath) return {}

   const parts = rawPath.split("/").filter(Boolean)
   let node = zipTree

   for (const part of parts) {
      const item = node[part]
      if (!item?.isDir) return {}
      node = item.children
   }

   return node
}

function buildBreadcrumbs(folderId) {
   if (!folderId) return []

   const rawPath = zipPathById[folderId]
   if (!rawPath) return []

   const parts = rawPath.split("/").filter(Boolean)

   return parts.map((name, index) => {
      const path = parts.slice(0, index + 1).join("/")

      return {
         name,
         id: zipIdByPath[path],
         fileId: zipIdByPath[path],
         raw_path: path
      }
   })
}

function base64Encode(str) {
   return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16))))
}

function makeDownloadUrl(entry, url) {
   const u = new URL(url)
   u.searchParams.set("zip_mode", "true")
   u.searchParams.set("offset", String(entry.offset))
   u.searchParams.set("compressed_size", String(entry.compressedSize))
   u.searchParams.set("uncompressed_size", String(entry.uncompressedSize))
   u.searchParams.set("compression_method", String(entry.compressionMethod))
   u.searchParams.set("filename", base64Encode(entry.filename))
   return u.toString()
}

function flatten(node, parentId, url) {
   return Object.values(node).map(item => {
      const entry = item.entry

      return {
         id: item.fileId,
         fileId: item.fileId,
         raw_path: item.raw_path,
         name: item.name,
         isDir: item.isDir,
         type: getFileType(item.name),
         extension: detectExtension(item.name),
         size: entry?.uncompressedSize || 0,
         parent_id: parentId || null,
         rawEntry: entry,
         thumbOff: true,
         download_url: entry ? makeDownloadUrl(entry, url) : null
      }
   })
}

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
         const fileId = zipIdByPath[path]

         return {
            id: fileId,
            fileId,
            raw_path: path,
            name,
            isDir: false,
            type: getFileType(name),
            extension: detectExtension(name),
            size: entry.uncompressedSize || 0,
            parent_id: parentPath ? zipIdByPath[parentPath] : null,
            rawEntry: entry,
            thumbOff: true,
            download_url: makeDownloadUrl(entry, url)
         }
      })
}

self.onmessage = async e => {
   const { type, payload = {} } = e.data || {}

   try {
      if (type === "init") {
         const { url, extensions } = payload
         if (!url) throw new Error("ZIP URL is required")

         baseUrl = url
         extensionMap = extensions || {}
         zipTree = {}
         zipEntriesMap = {}
         zipPathById = {}
         zipIdByPath = {}

         const reader = new zip.ZipReader(new zip.HttpReader(baseUrl, { useRangeHeader: true }))
         const generator = reader.getEntriesGenerator()
         const entries = []

         try {
            for await (const entry of generator) {
               if (entries.length >= MAX_ENTRIES) throw new Error("Zip archive has too many files")

               const rawPath = entry.filename.replace(/\/$/, "")
               if (!rawPath) continue

               entries.push({
                  fileId: await hashPath(rawPath),
                  raw_path: rawPath,
                  filename: entry.filename,
                  directory: Boolean(entry.directory),
                  compressionMethod: entry.compressionMethod,
                  compressedSize: Math.max(safeNumber(entry.compressedSize), 1),
                  uncompressedSize: safeNumber(entry.uncompressedSize),
                  offset: entry.offset
               })
            }
         } finally {
            await reader.close()
         }

         const built = await buildTree(entries)
         zipTree = built.root
         zipEntriesMap = built.map
         zipPathById = built.pathById
         zipIdByPath = built.idByPath

         self.postMessage({ type: "ready" })
         return
      }

      if (type === "list") {
         if (!baseUrl) throw new Error("Worker not initialized")

         const folderId = payload.fileId || null
         const node = resolveNode(folderId)
         const items = flatten(node, folderId, baseUrl)
         const breadcrumbs = buildBreadcrumbs(folderId)

         self.postMessage({ type: "list", items, breadcrumbs })
         return
      }

      if (type === "search") {
         if (!baseUrl) throw new Error("Worker not initialized")

         const items = searchEntries(payload.query, baseUrl)
         self.postMessage({ type: "search", items })
         return
      }

      throw new Error(`Unknown worker message type: ${String(type)}`)
   } catch (err) {
      self.postMessage({ type: "error", error: err?.message || String(err) })
   }
}