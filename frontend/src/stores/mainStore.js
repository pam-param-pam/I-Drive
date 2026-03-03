import { defineStore } from "pinia"
import i18n from "@/i18n/index.js"
import dayjs from "@/utils/dayjsSetup.js"

export const useMainStore = defineStore("main", {
   state: () => ({
      user: null,
      perms: null,
      settings: null,
      progress: 0,
      token: "",
      deviceId: "",
      loading: false,
      reload: false,
      selected: [],
      prompts: [],
      error: null,
      showShell: false,
      disabledCreation: false,
      folderPasswords: {},
      searchFilters: { "files": true, "folders": true },
      lastItem: null,
      searchActive: false,
      searchItems: [],
      breadcrumbs: [],
      currentFolder: null,
      items: [],
      shellSettings: {'showFileInfoInSidebar': false, 'printDebug': true, 'shellContent': []},
      usage: { used: 0, total: 0 },
      popupPreview: {},
      isFilesActive: false,
      deviceControlStatus: {"status": "unknown"},
      deviceControlOptions: {
         isVideoFullscreenActive: true,
         isVideoSubtitlesActive: true,
         isVideoSeekActive: true,
         isVideoToggleActive: true,
         isNavigationActive: true,
         isDeviceControlActive: true,
         isVideoVolumeChangeActive: true,
      },
      multiSelection: false,
      contextMenuState: {
         visible: false,
         advanced: false,
      },
      imagesBlock: {
         lastError: null,
         blockedUntil: null
      },
   }),

   persist: {
      key: "main:device-control",
      pick: ["deviceControlOptions"],
   },

   getters: {
      areImagesBlocked() {
         return (this.imagesBlock.blockedUntil && Date.now() < this.imagesBlock.blockedUntil)
      },
      isLogged() {
         return this.user !== null
      },
      getFolderPassword(state) {
         return function(folderId) {
            return state.folderPasswords[folderId] || null
         }
      },
      selectedCount() {
         return this.selected.length
      },
      previousPrompt() {
         return this.prompts.length > 1
            ? this.prompts[this.prompts.length - 2]
            : null
      },
      currentPrompt() {
         return this.prompts.length > 0
            ? this.prompts[this.prompts.length - 1]
            : null
      },
      currentPromptName() {
         return this.currentPrompt?.prompt
      },
      previousPromptName() {
         return this.previousPrompt?.prompt
      },
      sortedItems() {
         let items
         if (this.searchActive) {
            items = this.searchItems
         } else {
            items = this.items
         }
         if (!items || !this.settings) return

         let fieldName = this.settings.sortingBy
         let hideLocked = this.settings.hideLockedFolders
         let orderFactor = this.settings.sortByAsc ? 1 : -1
         let filteredItems
         if (hideLocked) {
            filteredItems = items.filter(item => !item.isLocked)
         } else {
            filteredItems = items.slice()
         }

         return filteredItems
            .sort((a, b) => {
               // 1. Folders First
               if (a.isDir !== b.isDir) {
                  return a.isDir ? -1 : 1
               }

               // 2. Sort by chosen field
               let fieldA = a[fieldName]
               let fieldB = b[fieldName]

               if (fieldA < fieldB) return orderFactor
               if (fieldA > fieldB) return -1 * orderFactor

               return 0
            })
            .map((item, index) => ({ ...item, index }))
      }

   },

   actions: {
      setIsFilesActive(value) {
         this.isFilesActive = value
      },
      setUsage(value) {
        this.usage = value
      },
      setShellSettings(value) {
         if (typeof value !== "object") {
            console.warn('setShellSettings must be object')
            return
         }
        this.shellSettings = value
      },
      clearShellContent() {
         this.shellSettings.shellContent = []
      },
      pushShellContent(result) {
        this.shellSettings.shellContent.push(result)
      },
      setSearchItems(items) {
         if (!items) items = []
         this.searchItems = items
      },
      setSearchActive(value) {
         this.searchActive = value
      },
      setCurrentFolderData(value) {
         this.setItems(value.folder.children)
         this.setBreadcrumbs(value.breadcrumbs)
         this.setCurrentFolder(value.folder)
      },
      setItems(value) {
         if (!value) value = []
         this.items = value
      },
      setBreadcrumbs(value) {
         this.breadcrumbs = value
      },
      setCurrentFolder(value) {
         this.currentFolder = value
      },
      setFolderPassword(payload) {
         this.folderPasswords[payload.folderId] = payload.password
      },
      resetFolderPassword() {
         this.folderPasswords = {}
      },
      setSearchFilters(payload) {
         this.searchFilters = payload
      },
      updateFolderPassword(payload) {
         this.folderPasswords[payload.folderId] = payload.password
      },
      setDisabledCreation(value) {
         this.disabledCreation = value
      },
      closeHover() {
         this.prompts.pop()
      },
      closeHovers() {
         this.prompts = []
      },
      setUnreadNotifications(value) {
        this.user.unreadNotifications = value
      },
      toggleShell() {
         this.showShell = !this.showShell
      },
      showHover(value) {
         if (typeof value !== "object") {
            this.prompts.push({
               prompt: value,
               confirm: null,
               props: null,
               cancel: null
            })
            return
         }

         this.prompts.push({
            prompt: value.prompt,
            confirm: value?.confirm,
            props: value?.props,
            cancel: value?.cancel
         })
      },
      setLoading(value) {
         this.loading = value
      },
      setToken(value) {
         this.token = value
      },
      setDeviceId(value) {
         this.deviceId = value
      },
      setUser(value) {
         if (value === null) {
            this.user = null
            return
         }
         this.user = value
      },
      setLastItem(value) {
         this.lastItem = value
      },
      setSelected(items) {
         this.selected = items
      },
      addSelected(value) {
         if (typeof value !== "object") return

         // Check if an object with the same 'file_id' already exists
         let exists = this.selected.some(item => item.id === value.id)

         if (exists) {
            console.warn(`Warning: Object with file_id ${value.id} already exists in the selected array.`)
            return
         }
         // If it doesn't exist, add the object to the array
         this.selected.push(value)
      },
      removeSelected(value) {
         this.selected = this.selected.filter(item => item.id !== value.id)
      },
      resetSelected() {
         this.selected = []
      },
      pushToItems(newItem) {
         if (this.items.length === 0) {
            this.items = [newItem]
            return
         }

         let exists = this.items.some(item => item.id === newItem.id)

         if (exists) {
            console.warn(`Item with ID ${newItem.id} already exists!`)
            return
         }
         this.items.push(newItem)
      },
      updateItem(newItem) {
         const index1 = this.items.findIndex(item => item.id === newItem.id)
         const index2 = this.selected.findIndex(item => item.id === newItem.id)
         const index3 = this.searchItems.findIndex(item => item.id === newItem.id)

         if (index1 !== -1) {
            this.items[index1] = newItem
         } else {
            console.warn(`Not found for id ${newItem.id}`)
         }

         if (index2 !== -1) {
            this.selected[index2] = newItem
         }

         if (index3 !== -1) {
            this.searchItems[index3] = newItem
         }
      },
      updateBreadcrumbsAndCurrentFolder(newItem) {
         if (this.currentFolder && this.currentFolder.id === newItem.id) {
            this.setCurrentFolder(newItem)
         }

         let changed = false

         const updated = this.breadcrumbs.map(bc => {
            if (bc.id === newItem.id && bc.name !== newItem.name) {
               changed = true
               return { ...bc, name: newItem.name }
            }
            return bc
         })

         if (changed) {
            this.setBreadcrumbs(updated)
         }

      },
      changeLockStatusAndPasswordCache({ folderId, newLockStatus, lockFrom }) {
         let index1 = this.items.findIndex(item => item.id === folderId)
         let index2 = this.selected.findIndex(item => item.id === folderId)

         if (index1 !== -1) {
            this.items[index1].isLocked = newLockStatus
            this.items[index1].lockFrom = lockFrom

         }
         if (index2 !== -1) {
            this.selected[index2].isLocked = newLockStatus
            this.selected[index2].lockFrom = lockFrom


         }
         this.updateFolderPassword({ folderId, password: null })
      },
      setPerms(value) {
         this.perms = value
      },
      setSortingBy(value) {
         this.settings.sortingBy = value
      },
      setSortByAsc(value) {
         this.settings.sortByAsc = value
      },
      setSettings(value) {
         let locale = value?.locale
         if (locale === "") {
            locale = i18n.detectLocale()
         }
         dayjs.locale(locale)
         i18n.global.locale = locale
         this.settings = value
      },
      setAnonState() {
         let locale = "pl"
         dayjs.locale(locale)
         i18n.global.locale = locale

         this.settings = { sortByAsc: false, sortingBy: "name", viewMode: "width grid", dateFormat: false, locale: locale }
         this.setTheme("dark")
      },
      updateSettings(value) {
         if (typeof value !== "object") return

         for (let field in value) {
            this.settings[field] = value[field]
         }

         let locale = value?.locale
         if (locale) {
            dayjs.locale(locale)
            i18n.global.locale = locale
         }
      },
      setError(value) {
         this.error = value
         this.loading = false
      },
      setTheme(theme) {
         this.settings.theme = theme
         let isDarkMode = false
         if (theme === "dark") isDarkMode = true
         document.body.classList.toggle("dark-mode", isDarkMode)

      },
      setPopupPreview(url) {
         this.popupPreview = url
      },
      clearPopupPreview() {
         this.popupPreview = null
      },
      setMultiSelection(value) {
         this.multiSelection = value
         if (!value) {
            this.resetSelected()
         }
      },
      openContextMenu({ pos, advanced = false }) {
         this.contextMenuState.visible = true
         this.contextMenuState.pos = pos
         this.contextMenuState.advanced = advanced
      },

      closeContextMenu() {
         this.contextMenuState.visible = false
      },
      blockImagesFor(seconds) {
         const ms = Number(seconds) * 1000
         if (!Number.isFinite(ms) || ms <= 0) return

         const candidate = Date.now() + ms

         if (!this.imagesBlock.blockedUntil || candidate > this.imagesBlock.blockedUntil) {
            this.imagesBlock.blockedUntil = candidate
         }

         this.imagesBlock.lastError = 429
      },
   }
})


