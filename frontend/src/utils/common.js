import {useMainStore} from "@/stores/mainStore.js"

export function sortItems(items) {
   return items
   // const store = useMainStore()

   // console.warn("====SORTING====")
   // // Create a shallow copy of the items array
   // let itemsCopy = items.slice()
   //
   // let sortingKey = store.settings.sortingBy
   // let isAscending = store.settings.sortByAsc
   // console.log(store.settings.sortingBy)
   // // Sort the items so directories come before files
   // itemsCopy.sort((a, b) => {
   //    // First, ensure directories come before files
   //    if (a.isDir && !b.isDir) return -1
   //    if (!a.isDir && b.isDir) return 1
   //
   //    // If both are directories or both are files, sort by the sorting key
   //    let aValue = a[sortingKey]
   //    let bValue = b[sortingKey]
   //
   //    if (isAscending) {
   //       return aValue < bValue ? -1 : aValue > bValue ? 1 : 0
   //    } else {
   //       return bValue < aValue ? -1 : bValue > aValue ? 1 : 0
   //    }
   // })
   //
   // // Add index property
   // itemsCopy.forEach((item, index) => {
   //   store.setItemIndex({id: item.id, index})
   // })

   // return itemsCopy
}

export function isMobile() {
   return window.innerWidth <= 950
}