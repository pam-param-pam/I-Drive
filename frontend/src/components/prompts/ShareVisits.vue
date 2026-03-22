<template>
   <div id="share" class="card floating scrollable-card">
      <div class="card-title">
         <h2>{{ $t("prompts.shareVisits") }}</h2>
      </div>

      <div class="card-content">
         <p v-if="visits.length" class="visits-summary">
            {{ $t("prompts.totalVisits") }}
            <code class="move-to">{{ share.name }}: {{ visits.length }}</code>
         </p>

         <div v-if="visits.length" class="share-table-container">
            <table>
               <thead>
               <tr>
                  <th>#</th>
                  <th>{{ $t("prompts.user") }}</th>
                  <th>{{ $t("prompts.accessAt") }}</th>
                  <th class="small"></th>
               </tr>
               </thead>

               <tbody>
               <tr
                  v-for="(visit, index) in sortedVisits"
                  :key="visit.id"
                  class="clickable-row"
                  @click="openEvents(visit)"
               >
                  <td class="index-cell">
                     {{ index + 1 }}.
                  </td>

                  <td>
                     {{ visit.user || "Anonymous" }}
                  </td>

                  <td>
                     {{ humanTime(visit.access_time) }}
                  </td>

                  <td class="small">
                     <button class="action" @click.stop="openEvents(visit)">
                        <i class="material-icons">chevron_right</i>
                     </button>
                  </td>
               </tr>
               </tbody>
            </table>
         </div>

         <p v-else>
            {{ $t("prompts.noShareVisits") }}
         </p>
      </div>

      <div class="card-action">
         <button class="button button--flat button--grey" @click="closeHover()">
            {{ $t("buttons.close") }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { humanTime } from "@/utils/common.js"
import { getVisitEvents } from "@/api/share.js"

export default {
   name: "ShareVisits",

   props: {
      share: { type: Object, required: true },
      visits: { type: Array, required: true }
   },
   computed: {
      sortedVisits() {
         return [...this.visits].sort((a, b) =>
            new Date(b.access_time) - new Date(a.access_time)
         )
      }
   },
   methods: {
      humanTime,
      ...mapActions(useMainStore, ["closeHover", "showHover"]),

      async openEvents(visit) {
         let events = await getVisitEvents(this.share.token, visit.id)
         this.showHover({
            prompt: "ShareVisitEvents",
            props: { "share": this.share, events, visit }
         })
      }
   }
}
</script>

<style scoped>
.card.floating {
  max-width: 30em !important;
}

.scrollable-card {
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.card-content {
  flex: 1;
  overflow: hidden;
}

.share-table-container {
  max-height: 55vh;
  overflow-y: auto;
  overflow-x: hidden;
}

.share-table-container table {
  width: 100%;
  border-collapse: collapse;
}

.share-table-container thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--surfacePrimary);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.6);
}

.clickable-row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.clickable-row:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.share-table-container td:nth-child(2),
.share-table-container th:nth-child(2) {
  padding-right: 2rem;
}

.index-cell {
  opacity: 0.6;
}
</style>