<template>
   <div class="card floating help">
      <div class="card-title">
         <h2>{{ $t("prompts.fileStats") }}</h2>
      </div>

      <div v-if="loaded && !isEmpty" class="card-content">
         <div class="file-stats-chart">
            <PieChart :data="stats" :options="options" />
         </div>
      </div>
      <div v-else-if="loaded" class="card-content">
         {{$t('prompts.noFileStats')}}
      </div>
      <div v-else class="card-content">
         {{$t('prompts.loadingChart')}}
      </div>

      <div class="card-action">
         <button
            :aria-label="$t('buttons.ok')"
            :title="$t('buttons.ok')"
            class="button button--flat"
            type="submit"
            @click="closeHover()"
         >
            {{ $t("buttons.ok") }}
         </button>
      </div>
   </div>
</template>

<script>
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"


import { ArcElement, Chart as ChartJS, Legend, Tooltip } from "chart.js"
import { Pie } from "vue-chartjs"
import { getFileStats } from "@/api/folder.js"
import { filesize } from "@/utils/common.js"

ChartJS.register(ArcElement, Tooltip, Legend)

export default {
   name: "FileStats",
   components: { PieChart: Pie },
   data() {
      return {
         rawStats: null,
         loaded: false,
         options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
               tooltip: {
                  displayColors: false,
                  callbacks: {
                     label: (tooltipItem) => {
                        let label = this.stats.labels ? this.stats.labels[tooltipItem.dataIndex] : ""

                        // safely get the data from rawStats
                        let item = this.rawStats && this.rawStats[label] ? this.rawStats[label] : { count: 0, total_size: 0 }

                        return [
                           item.count ? `Count: ${item.count}` : null,
                           `Size: ${filesize(item.total_size)}`
                        ].filter(Boolean)
                     }
                  }
               }
            }
         }
      }
   },
   computed: {
      ...mapState(useMainStore, ["currentFolder"]),
      isEmpty() {
         return Object.keys(this.rawStats).length === 0
      },
      stats() {
         const values = Object.values(this.rawStats)
         const useCounts = values.some(item => item.count > 0 && item.total_size === 0)
         return {
            labels: Object.keys(this.rawStats),
            datasets: [
               {
                  label: "File stats",
                  data: values.map(item => useCounts ? item.count : item.total_size),
                  backgroundColor: ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#C9CBCF", "#8BC34A", "#E91E63",
                     "#00BCD4", "#F44336", "#3F51B5", "#CDDC39", "#9C27B0", "#795548", "#607D8B", "#009688"]
               }
            ]
         }
      }
   },
   async created() {
      this.rawStats = await getFileStats(this.currentFolder.id)
      this.loaded = true
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"])
   }
}
</script>

<style scoped>
.file-stats-chart {
   position: relative;
   width: 100%;
   height: 280px;
}
</style>
