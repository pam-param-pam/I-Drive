<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.rename") }}</h2>
    </div>

    <div class="card-content">
      <p>
        {{ $t("prompts.renameMessage") }} <code>{{ oldName }}</code
      >:
      </p>
      <input
        class="input input--block"
        v-focus
        type="text"
        v-model.trim="name"
      />
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="closeHover()"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        @click="submit()"
        :disabled="!canSubmit"
        class="button button--flat"
        type="submit"
        :aria-label="$t('buttons.rename')"
        :title="$t('buttons.rename')"
      >
        {{ $t("buttons.rename") }}
      </button>
    </div>
  </div>
</template>

<script>
import {rename} from "@/api/item.js"
import throttle from "lodash.throttle"
import {useMainStore} from "@/stores/mainStore.js"
import {mapActions, mapState} from "pinia"

export default {
   name: "rename",
   data() {
      return {
         name: "",
         oldName: "",
      }
   },

   computed: {
      ...mapState(useMainStore, ["selected", "currentPrompt"]),
      canSubmit() {
         return this.name !== this.selected[0].name
      }

   },
   created() {
      this.name = this.selected[0].name
      this.oldName = this.name
   },
   methods: {
      ...mapActions(useMainStore, ["closeHover"]),

      submit: throttle(async function (event) {
         if (this.canSubmit) {

            let id = this.selected[0].id
            let new_name = this.name
            await rename({"id": id, "new_name": new_name})

            let message = this.$t('toasts.itemRenamed')
            this.$toast.success(message)

            if (this.currentPrompt.confirm) this.currentPrompt.confirm(new_name)

            this.closeHover()

         }
      }, 1000)
   },
}
</script>
