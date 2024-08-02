import store from "@/store"
import { baseURL } from "@/utils/constants"
import { encodePath } from "@/utils/url"
import vue from "@/utils/vue.js"
import {logout} from "@/utils/auth.js"

export function sortItems(items) {
  // Create a shallow copy of the items array
  const itemsCopy = items.slice()

  const sortingKey = store.state.settings.sortingBy
  const isAscending = store.state.settings.sortByAsc

  return itemsCopy.sort((a, b) => {
    let aValue = a[sortingKey]
    let bValue = b[sortingKey]

    if (isAscending) {
      return aValue < bValue ? -1 : aValue > bValue ? 1 : 0
    } else {
      return bValue < aValue ? -1 : bValue > aValue ? 1 : 0
    }
  })
}