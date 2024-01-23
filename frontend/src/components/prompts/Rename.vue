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
        @keyup.enter="submit"
        v-model.trim="name"
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

        @click="submit"
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
import {mapState, mapGetters} from "vuex";
import {rename} from "@/api/item.js";
import buttons from "@/utils/buttons.js";

export default {
  name: "rename",
  data: function () {
    return {
      name: "",
      oldName: "",
    };
  },

  computed: {
    ...mapState(["selected", "items"]),
    ...mapGetters(["isListing", "selectedCount"]),

  },
  created() {
    this.name = this.selected[0].name
    this.oldName = this.name
  },
  methods: {

    submit: async function () {

      try {

        await rename({"id": this.selected[0].id, "new_name": this.name});

        this.$store.commit("renameItem", {id: this.selected[0].id, newName: this.name});

        this.$toast.success(`${this.oldName} renamed to ${this.name}!`)

      } catch (error) {
        console.log(error)

      } finally {
        this.$store.commit("closeHovers");
        this.$store.commit("resetSelected");

      }
    },
  },
};
</script>
