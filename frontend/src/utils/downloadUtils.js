import { useMainStore } from "@/stores/mainStore.js"
import { getDownloader } from "@/transfers/downloads/Downloader.js"
import { createZIP } from "@/api/item.js"
import { createShareZIP } from "@/api/share.js"
import { showToast } from "@/utils/common.js"
import { useWebSocketStore } from "@/stores/websocketStore.js"
import { ClientsideDecryptionMethod } from "@/utils/constants.js"

export async function smartDownload() {
   const mainStore = useMainStore()
   const wsStore = useWebSocketStore()

   if (mainStore.selectedCount === 1 && !mainStore.selected[0].isDir) {
      let file = mainStore.selected[0]

      if (!mainStore.isLogged) {
         wsStore.send("share", JSON.stringify({ "type": "file_download", "args": { "file_id": file.id } }))
      }

      if (mainStore.settings.clientsideDecryptionMethod !== ClientsideDecryptionMethod.NO_DECRYPTION || !mainStore.isLogged) { //todo
         try {
            await getDownloader().downloadFile(file)
            return
         } catch (e) {
         }
      }

      window.open(mainStore.selected[0].download_url + "&download=true", "_blank")
      showToast("success", "toasts.downloadingSingle", {}, {name: file.name})
   } else {
      const ids = mainStore.selected.map((obj) => obj.id)
      let res
      if (!mainStore.isLogged) {
         res = await createShareZIP(mainStore.token, { ids: ids })
      } else {
         res = await createZIP({ ids: ids })
      }

      window.open(res.download_url, "_blank")
      showToast("success", "toasts.downloadingZIP")
   }
}
