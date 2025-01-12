<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.move") }}</h2>
    </div>

    <div class="card-content">
      <FolderList ref="fileList" @update:current="(val) => (dest = val)">
      </FolderList>
    </div>

    <div
      class="card-action"
      style="display: flex; align-items: center; justify-content: space-between;"
    >
      <template v-if="perms.create">
        <button
          class="button button--flat"
          @click="createDir()"
          :aria-label="$t('sidebar.newFolder')"
          :title="$t('sidebar.newFolder')"
          style="justify-self: left;"
        >
          <span>{{ $t("sidebar.newFolder") }}</span>
        </button>
      </template>
      <div>
        <button
          class="button button--flat button--grey"
          @click="closeHover()"
          :aria-label="$t('buttons.cancel')"
          :title="$t('buttons.cancel')"
        >
          {{ $t("buttons.cancel") }}
        </button>
        <button
          class="button button--flat"
          @click="submit"
          :disabled="isMoveDisabled"
          :aria-label="$t('buttons.move')"
          :title="$t('buttons.move')"
        >
          {{ $t("buttons.move") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import FolderList from "@/components/FolderList.vue"
import { move } from "@/api/item.js"
import throttle from "lodash.throttle"
import { mapActions, mapState } from "pinia"
import { useMainStore } from "@/stores/mainStore.js"

export default {
   name: "move",
   components: { FolderList },
   data() {
      return {
         dest: null
      }
   },
   computed: {
      ...mapState(useMainStore, ["perms", "selected"]),

      isMoveDisabled() {
         return this.selected[0].parent_id === this.dest?.id
      }
   },

   methods: {
      ...mapActions(useMainStore, ["closeHover", "addSelected", "showHover"]),
      createDir() {
         this.showHover({
            prompt: "newDir",
            props: {"folder": this.dest},
            confirm: (data) => {
               this.$refs.fileList.dirs.push(data)
            }
         })
      },
      submit: throttle(async function(event) {
         let ids = this.selected.map(obj => obj.id)
         let res = await move({ "ids": ids, "new_parent_id": this.dest.id })

         let message = this.$t("toasts.movingItems")
         this.$toast.info(message, {
            timeout: null,
            id: res.task_id
         })

         this.closeHover()

      }, 1000)
   }
}
</script>
