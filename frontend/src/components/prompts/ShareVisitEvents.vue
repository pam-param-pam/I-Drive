<template>
   <div id="share-events" class="card floating scrollable-card">

      <div class="card-title">
         <h2>{{ $t("prompts.visitEvents") }}</h2>
      </div>

      <div class="card-content">

         <p class="visits-summary ip-and-search">
            <span>
              {{ $t("prompts.visitEventsFor") }}:
              <code>{{ visit.user || "Anonymous" }}</code>
            </span>
            <span class="search-wrapper">
               <input
                  ref="typeInput"
                  v-model.trim="typeQuery"
                  class="input"
                  :aria-label="$t('prompts.searchForType')"
                  :placeholder="$t('prompts.searchForType')"
                  :title="$t('prompts.searchForType')"
                  autocomplete="off"
                  type="text"
               />
            <i v-if="typeQuery" class="material-icons clear-icon" @click="clearTypeSearch"> close </i>
           </span>
         </p>

         <p class="ip-and-search">
            <span>
              {{ $t("prompts.ip") }}: <code>{{ visit.ip }}</code>
            </span>
            <span class="search-wrapper">
                  <input
                     ref="metadataInput"
                     v-model.trim="metadataQuery"
                     class="input"
                     :aria-label="$t('prompts.searchForIds')"
                     :placeholder="$t('prompts.searchForIds')"
                     :title="$t('prompts.searchForIds')"
                     autocomplete="off"
                     type="text"
                  />
              <i v-if="metadataQuery" class="material-icons clear-icon" @click="clearMetadataSearch">close</i>
           </span>
         </p>

         <div v-if="events.length === 0">
            {{ $t("prompts.noVisitEvents") }}
         </div>

         <div v-else class="share-table-container">
            <table>
               <thead>
               <tr>
                  <th>#</th>
                  <th>{{ $t("prompts.type") }}</th>
                  <th>{{ $t("prompts.time") }}</th>
                  <th class="small"></th>
               </tr>
               </thead>

               <tbody>
               <template v-for="(event, index) in sortedEvents" :key="event.id">

                  <tr
                     class="clickable-row"
                     @click="toggleEvent(event.id)"
                  >
                     <td class="index-cell">
                        {{ index + 1 }}.
                     </td>

                     <td>{{ event.event_type }}</td>

                     <td>{{ humanTime(event.timestamp) }}</td>

                     <td class="small">
                        <button
                           class="action"
                           @click.stop="toggleEvent(event.id)"
                        >
                           <i class="material-icons">
                              {{ effectiveExpanded.includes(event.id)
                             ? "expand_less"
                             : "expand_more" }}
                           </i>
                        </button>
                     </td>
                  </tr>

                  <tr v-if="effectiveExpanded.includes(event.id)">
                     <td colspan="4">
                     <pre
                        class="event-metadata"
                        v-html="highlightedMetadata(event.metadata)"
                     ></pre>
                     </td>
                  </tr>

               </template>
               </tbody>
            </table>
         </div>

      </div>

      <div class="card-action">
         <button
            class="button button--flat button--blue"
            @click="closeHover()"
         >
            {{ $t("buttons.ok") }}
         </button>
      </div>

   </div>
</template>

<script>
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { humanTime } from "@/utils/common.js"

export default {
   name: "ShareVisitEvents",

   props: {
      share: { type: Object, required: true },
      visit: { type: Object, required: true },
      events: { type: Array, required: true }

   },

   data() {
      return {
         loadingEvents: false,
         expandedEvents: [],
         typeQuery: "",
         metadataQuery: ""
      }
   },
   computed: {
      sortedEvents() {
         let sorted = [...this.events].sort(
            (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
         )

         if (this.typeQuery) {
            const tq = this.typeQuery.toLowerCase()
            sorted = sorted.filter(e =>
               e.event_type?.toLowerCase().includes(tq)
            )
         }

         if (this.metadataQuery) {
            const mq = this.metadataQuery.toLowerCase()
            sorted = sorted.filter(e => {
               try {
                  return JSON.stringify(e.metadata)
                     .toLowerCase()
                     .includes(mq)
               } catch {
                  return false
               }
            })
         }

         return sorted
      },

      autoExpandedIds() {
         if (!this.metadataQuery) return []

         const mq = this.metadataQuery.toLowerCase()

         return this.events
            .filter(e => {
               try {
                  return JSON.stringify(e.metadata)
                     .toLowerCase()
                     .includes(mq)
               } catch {
                  return false
               }
            })
            .map(e => e.id)
      },

      effectiveExpanded() {
         if (this.metadataQuery) {
            return this.autoExpandedIds
         }
         return this.expandedEvents
      }
   },

   methods: {
      humanTime,
      ...mapActions(useMainStore, ["closeHover"]),
      clearTypeSearch() {
         this.typeQuery = ""
         this.$refs.typeInput?.focus()
      },

      clearMetadataSearch() {
         this.metadataQuery = ""
         this.$refs.metadataInput?.focus()
      },
      toggleEvent(eventId) {
         if (this.expandedEvents.includes(eventId)) {
            this.expandedEvents = this.expandedEvents.filter(id => id !== eventId)
         } else {
            this.expandedEvents.push(eventId)
         }
      },
      escapeHtml(str) {
         const div = document.createElement("div")
         div.textContent = str
         return div.innerHTML
      },

      highlight(text, query) {
         if (!query) return text
         const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
         const regex = new RegExp(`(${escapedQuery})`, "gi")
         return text.replace(regex, "<mark>$1</mark>")
      },

      highlightedMetadata(metadata) {
         let formatted
         try {
            formatted = JSON.stringify(metadata, null, 2)
         } catch {
            formatted = String(metadata)
         }

         const safe = this.escapeHtml(formatted)

         return this.highlight(safe, this.metadataQuery)
      }
   }
}
</script>
<style scoped>
.event-metadata mark {
 background: #ffcc00;
 color: black;
 padding: 0 2px;
 border-radius: 2px;
}

.card.floating {
 max-width: 35em !important;
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
   padding-right: 0.5em;
   padding-bottom: 1rem;
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

.index-cell {
 opacity: 0.6;
}

.clickable-row {
 cursor: pointer;
 transition: background-color 0.15s ease;
}

.clickable-row:hover {
 background-color: rgba(0, 0, 0, 0.05);
}

.event-metadata {
 background: var(--surfaceSecondary);
 padding: 0.75rem;
 font-size: 0.85rem;
 break-after: auto;
 white-space: pre-wrap;
 word-break: break-all;
 overflow-wrap: anywhere;
}

.ip-and-search {
 display: flex;
 justify-content: space-between;
 align-items: center;
 gap: 1rem;
 flex-wrap: wrap;
}

.search-wrapper {
 position: relative;
 display: flex;
 align-items: center;
}

.search-wrapper .input {
 padding-right: 4rem;
}

.clear-icon {
 position: absolute;
 right: 0.4rem;
 cursor: pointer;
 font-size: 18px;
 opacity: 0.6;
}

.clear-icon:hover {
 opacity: 1;
}

</style>