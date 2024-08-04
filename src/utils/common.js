import store from "@/store/index.js";

export function sortItems(items) {
  // Create a shallow copy of the items array
  const itemsCopy = items.slice()

  const sortingKey = store.state.settings.sortingBy
  const isAscending = store.state.settings.sortByAsc

  // Sort the items so directories come before files
  itemsCopy.sort((a, b) => {
    // First, ensure directories come before files
    if (a.isDir && !b.isDir) return -1
    if (!a.isDir && b.isDir) return 1

    // If both are directories or both are files, sort by the sorting key
    let aValue = a[sortingKey]
    let bValue = b[sortingKey]

    if (isAscending) {
      return aValue < bValue ? -1 : aValue > bValue ? 1 : 0
    } else {
      return bValue < aValue ? -1 : bValue > aValue ? 1 : 0
    }
  })

  // Add index property
  itemsCopy.forEach((item, index) => {
    store.commit('SET_ITEM_INDEX', {id: item.id, index})
  })

  return itemsCopy
}
export function isMobile() {
  console.log("isMobile")
  console.log(window.innerWidth <= 950)
  return window.innerWidth <= 950
}