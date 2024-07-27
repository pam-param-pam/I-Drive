<template>
  <errors v-if="error" :errorCode="error.response.status" />
  <div class="row" v-else-if="!loading">
    <div class="column">
      <div class="card">
        <div class="card-title">
          <h2>{{ $t("settings.shareManagement") }}</h2>
        </div>

        <div class="card-content full" v-if="shares.length > 0">
          <table>
            <tr>
              <th>{{ $t("settings.ShareName") }}</th>
              <th>{{ $t("settings.shareExpiry") }}</th>
              <th></th>
              <th></th>
            </tr>

            <tr v-for="share in shares" :key="share.token">
              <td>
                <a :href="buildLink(share)" target="_blank">{{ share.name }}</a>
              </td>
              <td>
                <template v-if="share.expire !== 0">{{
                  humanTime(share.expire)
                }}</template>
                <template v-else>{{ $t("permanent") }}</template>
              </td>
              <td class="small">
                <button
                  class="action"
                  @click="deleteLink($event, share)"
                  :aria-label="$t('buttons.delete')"
                  :title="$t('buttons.delete')"
                >
                  <i class="material-icons">delete</i>
                </button>
              </td>
              <td class="small">
                <button
                  class="action copy-clipboard"
                  :data-clipboard-text="buildLink(share)"
                  :aria-label="$t('buttons.copyToClipboard')"
                  :title="$t('buttons.copyToClipboard')"
                >
                  <i class="material-icons">content_paste</i>
                </button>
              </td>
            </tr>
          </table>
        </div>
        <h2 class="message" v-else>
          <i class="material-icons">sentiment_dissatisfied</i>
          <span>{{ $t("files.lonely") }}</span>
        </h2>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState, mapMutations } from "vuex"
import moment from "moment/min/moment-with-locales.js"
import Clipboard from "clipboard"
import Errors from "@/views/Errors.vue"
import {getAllShares, removeShare} from "@/api/share.js"

export default {
  name: "shares",
  components: {
    Errors,
  },
  computed: mapState(["user", "settings", "perms", "loading"]),

  data() {
    return {
      error: null,
      shares: [],
      clip: null,
    }
  },
  async created() {

    this.setLoading(true)

    let links = await getAllShares()

    this.shares = links
    this.setLoading(false)

    

  },
  mounted() {
    this.clip = new Clipboard(".copy-clipboard")
    this.clip.on("success", () => {
      this.$toast.success(this.$t("success.linkCopied"))
    })
  },
  beforeDestroy() {
    this.clip.destroy()
  },
  methods: {
    ...mapMutations(["setLoading"]),
    deleteLink: async function (event, share) {
      event.preventDefault()

      this.$store.commit("showHover", {
        prompt: "share-delete",
        confirm: () => {
          this.$store.commit("closeHover")

          removeShare({"token": share.token})
          this.shares = this.shares.filter((item) => item.token !== share.token)
          this.$toast.success(this.$t("toasts.shareDeleted"))

        },
      })
    },
    humanTime(time) {
      //todo czm globalny local nie dzIała?
      let locale = this.settings?.locale || "en"

      moment.locale(locale)
      // Parse the target date
      return moment(time, "YYYY-MM-DD HH:mm").endOf('second').fromNow()
    },
    buildLink(share) {

      return "/share/" + share.token

    },

  },
}
</script>
