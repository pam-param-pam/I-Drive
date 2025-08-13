<template>
  <div id="share" class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.shareVisits") }}</h2>
    </div>

    <template v-if="visits.length > 0">
      <div class="card-content">
        <p>
          {{ $t("prompts.totalVisits") }} <code class="move-to">{{ share.name }}: {{ visits.length }}</code>
        </p>
        <div class="share-table-container">
          <table>
            <tr>
              <th>#</th>
              <th>{{ $t("prompts.user") }}</th>
              <th>{{ $t("prompts.count") }}</th>
              <th>{{ $t("prompts.lastAccess") }}</th>
            </tr>

            <tr v-for="(visit, index) in visits">
              <td>{{ index + 1 }}</td>
              <td :title="`IP: ${visit.ip}, Agent: ${visit.user_agent}`">
                {{ visit.user }}
              </td>
              <td>
                {{ visit.access_count || '-' }}
              </td>
              <td>
                {{ humanTime(visit.last_access_time) }}
              </td>
            </tr>
          </table>
        </div>
      </div>

      <div class="card-action">
        <button
          :aria-label="$t('buttons.close')"
          :title="$t('buttons.close')"
          class="button button--flat button--grey"
          @click="closeHover()"
        >
          {{ $t("buttons.close") }}
        </button>
      </div>
    </template>
    <div v-else>
      <p>
        {{ $t("prompts.noShareVisits") }}
      </p>
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { humanTime } from "@/utils/common.js"

export default {
   name: "ShareAccesses",

   props: {
      share: {
         type: {},
         required: true
      },
      visits: {
         type: Array,
         required: true
      }

   },
   computed: {
      ...mapState(useMainStore, ["settings"])
   },
   methods: {
      humanTime,
      ...mapActions(useMainStore, ["closeHover"]),

   }
}
</script>

<style scoped>

</style>