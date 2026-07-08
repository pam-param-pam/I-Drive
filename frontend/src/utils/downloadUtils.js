import { useMainStore } from "@/stores/mainStore.js"
import { getDownloader } from "@/transfers/downloads/Downloader.js"
import { createZIP } from "@/api/item.js"
import { createShareZIP } from "@/api/share.js"
import { showToast } from "@/utils/common.js"
import { useWebSocketStore } from "@/stores/websocketStore.js"
import { ClientsideDecryptionMethod } from "@/utils/constants.js"
import { FilePickerNotSupported } from "@/transfers/downloads/utils/helper.js"
import { isAxiosError } from "axios"

export async function smartDownload(shareToken) {
   const mainStore = useMainStore()
   const wsStore = useWebSocketStore()

   const selected = mainStore.selected
   const isSingleFile = mainStore.selectedCount === 1 && !selected[0].isDir
   const requiresClientSideDownload =
      mainStore.settings.clientsideDecryptionMethod !== ClientsideDecryptionMethod.NO_DECRYPTION || shareToken

   if (isSingleFile) {
      await downloadSingleFile({
         file: selected[0],
         wsStore,
         requiresClientSideDownload,
         shareToken
      })
      return
   }

   await downloadZip({
      ids: selected.map(item => item.id),
      requiresClientSideDownload,
      shareToken
   })
}


async function downloadSingleFile({ file, wsStore, requiresClientSideDownload, shareToken }) {
   if (shareToken) {
      wsStore.send("share", JSON.stringify({ type: "file_download", args: { file_id: file.id } }))
   }

   if (requiresClientSideDownload) {
      try {
         await getDownloader().downloadFile(file)
         return
      } catch (error) {
         console.warn("Client-side file download failed", error)
         if (!(error instanceof FilePickerNotSupported || isAxiosError(error) || "aborted" in error.message)) {
            showToast("error", error.message)
            return
         }
      }
   }

   window.open(`${file.download_url}&download=true`, "_blank")
   showToast("success", "toasts.downloadingSingle", {}, { name: file.name })
}


async function downloadZip({ ids, requiresClientSideDownload, shareToken }) {
   console.log("downloadZip")
   if (requiresClientSideDownload) {
      console.log("requiresClientSideDownload")
      try {
         await getDownloader().downloadZip(ids, shareToken)
         return
      } catch (error) {
         console.warn("Client-side ZIP download failed", error)
         if (!(error instanceof FilePickerNotSupported || isAxiosError(error) || "aborted" in error.message)) {
            showToast("error", error.message)
            return
         }
      }
   }

   const response = !shareToken ? await createZIP({ ids }) : await createShareZIP(shareToken, { ids })
   console.log(response)
   window.open(response.download_url, "_blank")
   showToast("success", "toasts.downloadingZIP")
}
