<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.irreversibleAction") }}</h2>
    </div>
    <div class="card-content">
      <p v-if="selectedCount === 1">
        {{ $t("prompts.deleteMessageSingle") }}
      </p>
      <p v-else-if="selectedCount > 1">
        {{ $t("prompts.deleteMessageMultiple", {count: selectedCount}) }}
      </p>

    </div>
    <div class="card-action">
      <button
        @click="$store.commit('closeHover')"
        class="button button--flat button--grey"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        @click="submit"
        class="button button--flat button--red"
        :aria-label="$t('buttons.delete')"
        :title="$t('buttons.delete')"
      >
        {{ $t("buttons.delete") }}
      </button>

    </div>
  </div>
</template>

<script>
import {mapGetters, mapMutations, mapState} from "vuex"
import {remove} from "@/api/item.js"

export default {
  name: "delete",
  computed: {
    ...mapGetters(["selectedCount", "currentPrompt"]),
    ...mapState(["selected", "items"]),
  },

  methods: {
    ...mapMutations(["closeHover", "resetSelected"]),
    async submit() {
      try {
        let ids = this.selected.map(item => item.id)

        let res = await remove({"ids": ids})

        let message = this.$t('toasts.itemsAreBeingDeleted', {amount: ids.length})
        this.$toast.info(message, {
          timeout: null,
          id: res.task_id,
        })
        if (this.currentPrompt.confirm) this.currentPrompt.confirm()

      }
      finally {
        this.resetSelected()
        this.closeHover()
        //this.$store.commit("setReload", true)

      }
    },

  },
}
</script>
