
self.onmessage = async (event) => {


      let requestGenerator = event.data
      let generated = await requestGenerator.next()

      postMessage()

}
