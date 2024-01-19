<template>
  <div class="card floating">
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
        @click="$store.commit('closeHovers')"
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
import {mapGetters, mapMutations, mapState} from "vuex";
import {remove} from "@/api/item.js";

export default {
  name: "delete",
  computed: {
    ...mapGetters(["selectedCount", "currentPrompt"]),
    ...mapState(["selected"]),
  },
  methods: {
    ...mapMutations(["closeHovers"]),
    submit: async function () {

      try {
        let ids = this.selected.map(item => item.id);

        await remove({"ids": ids});

        this.closeHovers();
        this.$store.commit("setReload", true);


      }
      catch (e) {
        this.$showError(e);
      }
    },
  },
};
</script>
