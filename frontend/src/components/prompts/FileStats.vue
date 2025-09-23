<template>
  <div class="card floating help">
    <div class="card-title">
      <h2>{{ $t("prompts.fileStats") }}</h2>
    </div>

    <div class="card-content" v-if="stats">
      <PieChart :data="stats" :options="options" />
    </div>
    <div class="card-content" v-else>
      Loading chart...
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
import { filesize } from "@/utils/index.js"
import { getFileStats } from "@/api/folder.js"

ChartJS.register(ArcElement, Tooltip, Legend)

export default {
   name: "FileStats",
   components: { PieChart: Pie },
   data() {
      return {
         stats: null,
         rawStats: null,
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
      ...mapState(useMainStore, ["currentFolder"])
   },
   async created() {
      this.rawStats = await getFileStats(this.currentFolder.id)
      this.stats = {
         labels: Object.keys(this.rawStats),
         datasets: [
            {
               label: "File stats",
               data: Object.values(this.rawStats).map(item => item.total_size),
               backgroundColor: ["#FF6384","#36A2EB","#FFCE56","#4BC0C0","#9966FF","#FF9F40","#C9CBCF","#8BC34A","#E91E63",
                  "#00BCD4","#F44336","#3F51B5","#CDDC39","#9C27B0","#795548","#607D8B","#009688"]
            }
         ]
      }

   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"])

   }
}
</script>
