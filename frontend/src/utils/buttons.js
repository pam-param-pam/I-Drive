function loading(button) {

   let el = document.querySelector(`#${button}-button > i`)

   if (el === undefined || el === null) {
      console.log('Error getting button ' + button) // eslint-disable-line
      return
   }

   if (el.innerHTML === "autorenew" || el.innerHTML === "done") {
      return
   }

   el.dataset.icon = el.innerHTML
   el.style.opacity = 0

   setTimeout(() => {
      el.classList.add("spin")
      el.innerHTML = "autorenew"
      el.style.opacity = 1
   }, 100)


}

function success(button) {

   let el = document.querySelector(`#${button}-button > i`)

   if (el === undefined || el === null) {
      console.log('Error getting button ' + button)
      return
   }

   el.style.opacity = 0

   setTimeout(() => {
      el.classList.remove("spin")
      let prev_icon = el.innerHTML
      el.innerHTML = "done"
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
   success,
}
