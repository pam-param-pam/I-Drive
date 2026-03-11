import { createI18n } from "vue-i18n"
import en from "./locals/en.json"
import pl from "./locals/pl.json"
import uwu from "./locals/uwu.json"

export function detectLocale() {
   let locale = (navigator.language || navigator.browserLanguage).toLowerCase()
   switch (true) {
      case /^en.*/i.test(locale):
         locale = "en"
         break
      case /^pl.*/i.test(locale):
         locale = "pl"
         break
      case /^uwu.*/i.test(locale):
         locale = "uwu"
         break
      default:
         locale = "en"
   }
   return locale
}


const removeEmpty = (obj) =>
   Object.keys(obj)
      .filter((k) => obj[k] !== null && obj[k] !== undefined && obj[k] !== "")
      .reduce(
         (newObj, k) =>
            typeof obj[k] === "object"
               ? Object.assign(newObj, { [k]: removeEmpty(obj[k]) })
               : Object.assign(newObj, { [k]: obj[k] }),
         {}
      )


const i18n = createI18n({
   locale: detectLocale(),
   fallbackLocale: "en",
   messages: {
      en: en,
      pl: removeEmpty(pl),
      uwu: removeEmpty(uwu)
   }
})

export default i18n
