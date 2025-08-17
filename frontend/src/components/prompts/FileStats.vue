<template>
  <div class="card floating help">
    <div class="card-title">
      <h2>{{ $t('prompts.fileStats') }}</h2>
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
        {{ $t('buttons.ok') }}
      </button>
    </div>
  </div>
</template>

<script>
import { mapActions } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"
import { getFileStats } from "@/api/user.js"


import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { Pie } from 'vue-chartjs'
import { filesize } from "@/utils/index.js"

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
                        const label = this.stats.labels ? this.stats.labels[tooltipItem.dataIndex] : ''

                        // safely get the data from rawStats
                        const item = this.rawStats && this.rawStats[label] ? this.rawStats[label] : { count: 0, total_size: 0 }

                        return [
                           `Count: ${item.count}`,
                           `Size: ${filesize(item.total_size)}`
                        ]
                     }
                  }
               }
            }
         },
      }
   },
   async created() {
      this.rawStats = await getFileStats()
      this.stats = {
         labels: Object.keys(this.rawStats),              // ['files', 'folders']
         datasets: [
            {
               label: 'File stats',
               data: Object.values(this.rawStats).map(item => item.total_size),
               backgroundColor: ['#FF6384', '#36A2EB'] // add colors
            }
         ]
      }
      console.log(this.stats)

   },
   methods: {
      ...mapActions(useMainStore, ['closeHover']),

   }
}
</script>
