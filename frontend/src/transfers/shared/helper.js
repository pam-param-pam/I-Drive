export const beforeUnloadEvent = event => {
   event.preventDefault()
   event.returnValue = ""
}