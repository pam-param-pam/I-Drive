import {partial} from "filesize"
import moment from 'moment/min/moment-with-locales.js'
import { useMainStore } from "@/stores/mainStore.js"

/**
 * Formats filesize as KiB/MiB/...
 */
export const filesize = partial()

// export function humanTime(date) {
//todo
//    const mainStore = useMainStore()
//
//    if (mainStore.settings.dateFormat) {
//       return moment(date, 'YYYY-MM-DD HH:mm').format('DD/MM/YYYY, hh:mm')
//    }
//    //todo czm globalny local nie dzIała?
//    let locale = this.settings?.locale || 'en'
//
//    moment.locale(locale)
//    // Parse the target date
//    return moment(date, 'YYYY-MM-DD HH:mm').endOf('second').fromNow()
// }