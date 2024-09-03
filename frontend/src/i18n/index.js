import {createI18n} from 'vue-i18n'
import en from './en.json'
import pl from './pl.json'
import uwu from './uwu.json'

// Detect the locale based on the browser settings
export function detectLocale() {
   let locale = (navigator.language || navigator.browserLanguage).toLowerCase()
   switch (true) {
      case /^en.*/i.test(locale):
         locale = 'en'
         break
      case /^pl.*/i.test(locale):
         locale = 'pl'
         break
      case /^uwu.*/i.test(locale):
         locale = 'uwu'
         break
      default:
         locale = 'en'
   }
   return locale
}

// Remove empty values recursively from the object
const removeEmpty = (obj) =>
   Object.keys(obj)
      .filter((k) => obj[k] !== null && obj[k] !== undefined && obj[k] !== '') // Remove undefined, null, and empty string
      .reduce(
         (newObj, k) =>
            typeof obj[k] === 'object'
               ? Object.assign(newObj, {[k]: removeEmpty(obj[k])}) // Recurse
               : Object.assign(newObj, {[k]: obj[k]}), // Copy value
         {}
      )


// Create the i18n instance with the locale and messages
const i18n = createI18n({
   locale: detectLocale(),
   fallbackLocale: 'en',
   messages: {
      en: en,
      pl: removeEmpty(pl),
      uwu: removeEmpty(uwu),
   },
})

export default i18n
