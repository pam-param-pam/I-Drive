<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.newFile") }}</h2>
    </div>

    <div class="card-content">
      <p>{{ $t("prompts.newFileMessage") }}</p>
      <input
        class="input input--block"
        v-focus
        type="text"
        @keyup.enter="submit"
        v-model.trim="name"
      />
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="$store.commit('closeHover')"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        class="button button--flat"
        @click="submit"
        :aria-label="$t('buttons.create')"
        :title="$t('buttons.create')"
      >
        {{ $t("buttons.create") }}
      </button>
    </div>
  </div>
</template>

<script>
import { mapGetters } from "vuex"


export default {
  name: "new-file",
  data() {
    return {
      name: "",
    }
  },
  computed: {
    ...mapGetters(["isFiles", "isListing"]),
  },
  methods: {
    async submit(event) {

    },
  },
}
</script>
