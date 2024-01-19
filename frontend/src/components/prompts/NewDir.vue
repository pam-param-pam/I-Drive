<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.newDir") }}</h2>
    </div>

    <div class="card-content">
      <p>{{ $t("prompts.newDirMessage") }}</p>
      <input
        class="input input--block"
        type="text"
        @keyup.enter="submit"
        v-model.trim="name"
        v-focus
      />
    </div>

    <div class="card-action">
      <button
        class="button button--flat button--grey"
        @click="$store.commit('closeHovers')"
        :aria-label="$t('buttons.cancel')"
        :title="$t('buttons.cancel')"
      >
        {{ $t("buttons.cancel") }}
      </button>
      <button
        class="button button--flat"
        :aria-label="$t('buttons.create')"
        :title="$t('buttons.create')"
        @click="submit"
      >
        {{ $t("buttons.create") }}
      </button>
    </div>
  </div>
</template>

<script>
import {mapState} from "vuex";

import {create} from "@/api/folder.js";

export default {
  name: "new-dir",
  props: {
    redirect: {
      type: Boolean,
      default: true,
    },
    base: {
      type: [String, null],
      default: null,
    },
  },
  data: function () {
    return {
      name: "",
    };
  },
  computed: {
    ...mapState(["currentFolder"]),
  },
  methods: {
    submit: async function (event) {
      event.preventDefault();
      try {
        await create({"parent_id": this.currentFolder.id, "name": this.name})
        this.$showSuccess("woo");

      }
      catch (error) {
        this.$showError(error);
      }
      this.$store.commit("setReload", true);

      this.$store.commit("closeHovers");
    },
  },
};
</script>
