import { defineStore } from "pinia"
import moment from "moment"
import i18n from "@/i18n/index.js"
import { updateSettings } from "@/api/user.js"

export const useMainStore = defineStore("main", {
   state: () => ({
      user: null,
      perms: null,
      settings: null,
      progress: 0,
      token: "",
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

      breadcrumbs: [],
      currentFolder: null,
      items: []

   }),

   getters: {

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
      previousPrompt(state) {
         return state.prompts.length > 1
            ? state.prompts[state.prompts.length - 2]
            : null
      },
      currentPrompt(state) {
         return state.prompts.length > 0
            ? state.prompts[state.prompts.length - 1]
            : null
      },
      currentPromptName(state, getters) {
         return this.currentPrompt?.prompt
      },
      previousPromptName(state, getters) {
         return this.previousPrompt?.prompt
      },
      sortedItems() {
         let allItems = []
         console.log(this.items)
         if (this.items != null) {
            this.items.forEach((item) => {
               if (item.isDir && (!item.isLocked || !this.settings.hideLockedFolders)) {
                  allItems.push({ ...item, isDir: true })
               } else if (!item.isDir) {
                  allItems.push({ ...item, isDir: false })
               }
            })
         }
         // Sort the combined array, placing directories first
         allItems.sort((a, b) => {
            if (a.isDir && !b.isDir) return -1 // Folders come first
            if (!a.isDir && b.isDir) return 1  // Files come after
            return 0                           // Keep the original order otherwise
         })

         return allItems
      }

   },

   actions: {
      setCurrentFolderData(value) {
         console.log("setCurrentFolderData")

         this.setItems(value.folder.children)
         this.setBreadcrumbs(value.breadcrumbs)
         this.setCurrentFolder(value.folder)

      },
      setItems(value) {
         console.log("setting items")
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
      setDisabledCreation(payload) {
         this.disabledCreation = payload
      },
      closeHover() {
         this.prompts.pop()
      },
      closeHovers() {
         this.prompts = []
      },
      toggleShell() {
         this.showShell = !this.showShell
      },
      showHover(value) {
         if (typeof value !== "object") {
            this.prompts.push({
               prompt: value,
               confirm: null,
               action: null,
               props: null,
               cancel: null
            })
            return
         }

         this.prompts.push({
            prompt: value.prompt,
            confirm: value?.confirm,
            action: value?.action,
            props: value?.props,
            cancel: value?.cancel
         })
      },
      setLoading(value) {
         console.log("setting loading")
         console.log(value)
         this.loading = value
      },
      setToken(value) {
         this.token = value
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
      addSelected(value) {
         console.log("addSelected")
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
      updateItems(value) {
         this.items.push(value)
      },

      renameItem({ id, newName }) {
         const index1 = this.items.findIndex(item => item.id === id)
         const index2 = this.selected.findIndex(item => item.id === id)

         if (index1 !== -1) {
            this.items[index1].name = newName
         }
         if (index2 !== -1) {
            this.selected[index2].name = newName
         }
      },
      changeLockStatusAndPasswordCache({ folderId, newLockStatus, lockFrom }) {
         const index1 = this.items.findIndex(item => item.id === folderId)
         const index2 = this.selected.findIndex(item => item.id === folderId)

         if (index1 !== -1) {
            this.items[index1].isLocked = newLockStatus
            this.items[index1].lockFrom = lockFrom

         }
         if (index2 !== -1) {
            this.selected[index2].isLocked = newLockStatus
            this.items[index2].isLocked = newLockStatus
            this.items[index2].lockFrom = lockFrom


         }
         this.updateFolderPassword({ folderId, password: null })
      },
      updatePreviewInfo({ id, iso, focal_length, aperture, model_name, exposure_time }) {
         const index1 = this.items.findIndex(item => item.id === id)
         const index2 = this.selected.findIndex(item => item.id === id)

         if (index1 !== -1) {
            this.items[index1].iso = iso
            this.items[index1].focal_length = focal_length
            this.items[index1].aperture = aperture
            this.items[index1].model_name = model_name
            this.items[index1].exposure_time = exposure_time
         }
         if (index2 !== -1) {
            this.selected[index2].iso = iso
            this.selected[index2].focal_length = focal_length
            this.selected[index2].aperture = aperture
            this.selected[index2].model_name = model_name
            this.selected[index2].exposure_time = exposure_time
         }
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
         console.log("finished settings")

         let locale = value?.locale
         if (locale === "") {
            locale = i18n.detectLocale()
         }
         moment.locale(locale)
         i18n.global.locale = locale
         this.settings = value
      },
      setAnonState() {
         const country = "pl"
         moment.locale(country)
         i18n.global.locale = country
         this.settings = { sortByAsc: false, sortingBy: "name", viewMode: "list", dateFormat: false, locale: country }
      },
      updateSettings(value) {
         if (typeof value !== "object") return

         for (let field in value) {
            this.settings[field] = value[field]
         }

         let locale = value?.locale
         if (locale) {
            moment.locale(locale)
            i18n.global.locale = locale
         }
         console.log("update settings")
      },
      setError(value) {
         this.error = value
         this.loading = false
      },
      setTheme(theme) {
         this.settings.theme = theme
         let isDarkMode = false
         if (theme === "dark") isDarkMode=true
         document.body.classList.toggle("dark-mode", isDarkMode);

      }
   }
})


