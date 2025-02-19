function getButton(name) {
   let selector = `#${name}-button > i`
   let el = document.querySelector(selector)

   if (el === undefined || el === null) {
      throw Error(`Error getting ${selector}`)
   }
   return el
}

function loading(button) {
   let el = getButton(button)

   if (el.innerHTML === 'autorenew' || el.innerHTML === 'done') {
      return
   }

   el.dataset.icon = el.innerHTML
   el.style.opacity = 0

   setTimeout(() => {
      el.classList.add('spin')
      el.innerHTML = 'autorenew'
      el.style.opacity = 1
   }, 100)
}

function success(button) {
   let el = getButton(button)

   el.style.opacity = 0

   setTimeout(() => {
      el.classList.remove('spin')
      let prev_icon = el.innerHTML
      el.innerHTML = 'done'
      el.style.opacity = 1

      setTimeout(() => {
         el.style.opacity = 0

         setTimeout(() => {
            el.innerHTML = prev_icon
            el.style.opacity = 1
         }, 100)
      }, 2000)
   }, 100)
}

export default {
   loading,
   success
}
