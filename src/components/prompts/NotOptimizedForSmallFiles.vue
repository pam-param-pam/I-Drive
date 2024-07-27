<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.iDriveNotOptimized") }}</h2>
    </div>
    <div class="card-content">
      <p>
        {{ $t("prompts.iDriveNotOptimizedMessage") }}
      </p>


    </div>
    <div class="card-action">
      <button
        @click="$store.commit('closeHover')"
        class="button button--flat button--grey"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.ok") }}
      </button>
      <button
        @click="submit"
        class="button button--flat button--red"
        :aria-label="$t('buttons.delete')"
        :title="$t('buttons.delete')"
      >
        {{ $t("buttons.proceedAnyway") }}
      </button>

    </div>
  </div>
</template>

<script>
import {mapGetters, mapMutations} from "vuex"

export default {
  name: "NotOptimizedForSmallFiles",
  computed: {
    ...mapGetters(["currentPrompt"]),
  },
  methods: {
    ...mapMutations(["closeHover"]),

    submit: async function () {

      this.currentPrompt?.confirm()
      this.closeHover()

    },
  },
}
</script>
