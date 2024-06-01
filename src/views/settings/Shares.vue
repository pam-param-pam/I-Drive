<template>
  <errors v-if="error" :errorCode="error.status" />
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
import { share as api } from "@/api"
import { mapState, mapMutations } from "vuex"
import moment from "moment"
import Clipboard from "clipboard"
import Errors from "@/views/Errors.vue"

export default {
  name: "shares",
  components: {
    Errors,
  },
  computed: mapState(["user", "perms", "loading"]),
  data: function () {
    return {
      error: null,
      shares: [],
      clip: null,
    }
  },
  async created() {

    this.setLoading(true)

    try {
      let links = await api.getAllShares()
      /*
      if (this.perms.admin) {
        let userMap = new Map()
        for (let user of await users.getAllShares())
          userMap.set(user.id, user.username)
        for (let link of shares)
          link.username = userMap.has(link.userID)
            ? userMap.get(link.userID)
            : ""
      }

       */
      this.shares = links
    } catch (e) {
      this.error = e
    } finally {
      this.setLoading(false)
    }
    

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

          try {
            api.removeShare({"token": share.token})
            this.shares = this.shares.filter((item) => item.token !== share.token)
            this.$toast.success(this.$t("toasts.shareDeleted"))
          } catch (e) {
            console.log(e)
          }
        },
      })
    },
    humanTime(time) {
      return moment(time).fromNow()
    },
    buildLink(share) {

      return "/share/" + share.token

    },

  },
}
</script>
