<template>
  <div id="share" class="card floating">
    <div class="card-title">
      <h2>{{ $t('prompts.shareVisits') }}</h2>
    </div>

    <template v-if="visits.length > 0">
      <div class="card-content">
        <p>
          {{ $t('prompts.totalVisits') }} <code class="move-to">{{ share.name }}: {{ visits.length }}</code>
        </p>
        <div class="share-table-container">
          <table>
            <tr>
              <th>#</th>
              <th>{{ $t('prompts.user') }}</th>
              <th>{{ $t('prompts.count') }}</th>
              <th>{{ $t('prompts.lastAccess') }}</th>
            </tr>

            <tr v-for="(visit, index) in visits">
              <td>{{ index + 1 }}</td>
              <td :title="`IP: ${visit.ip}, Agent: ${visit.user_agent}`">
                {{visit.user}}
              </td>
              <td>
                {{visit.access_count}}
              </td>
              <td>
                {{humanTime(visit.last_access_time)}}
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
          {{ $t('buttons.close') }}
        </button>
      </div>
    </template>
    <div v-else>
      <p>
        {{ $t('prompts.noShareVisits') }}
      </p>
    </div>
  </div>
</template>

<script>
import dayjs from "@/utils/dayjsSetup.js"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "ShareAccesses",

   props: {
      share: {
         type: {},
         required: true
      },
      visits: {
         type: [],
         required: true
      }

   },
   computed: {
      ...mapState(useMainStore, ['settings'])
   },
   methods: {
      ...mapActions(useMainStore, ['closeHover']),

      humanTime(date) {
         if (this.settings.dateFormat) {
            return dayjs(date, "YYYY-MM-DD HH:mm").format("DD/MM/YYYY, hh:mm")
         }
         return dayjs(date, "YYYY-MM-DD HH:mm").fromNow()
      }
   }
}
</script>

<style scoped>

</style>