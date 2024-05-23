import Vue from "vue"
import VueI18n from "vue-i18n"


import en from "./en.json"
import pl from "./pl.json"
import uwu from "./uwu.json"


Vue.use(VueI18n)

export function detectLocale() {
  let locale = (navigator.language || navigator.browserLangugae).toLowerCase();
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

  return locale;
}

const removeEmpty = (obj) =>
  Object.keys(obj)
    .filter((k) => obj[k] !== null && obj[k] !== undefined && obj[k] !== "") // Remove undef. and null and empty.string.
    .reduce(
      (newObj, k) =>
        typeof obj[k] === "object"
          ? Object.assign(newObj, { [k]: removeEmpty(obj[k]) }) // Recurse.
          : Object.assign(newObj, { [k]: obj[k] }), // Copy value.
      {}
    );

export const rtlLanguages = [];

const i18n = new VueI18n({
  locale: detectLocale(),
  fallbackLocale: "en",
  messages: {

    en: en,
    pl: removeEmpty(pl),
    uwu: removeEmpty(uwu),


  },
});

export default i18n;
