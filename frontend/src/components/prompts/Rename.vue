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

    <div class="card-action" >
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
import { mapState, mapGetters } from "vuex";
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
    ...mapState(["selected"]),
    ...mapGetters(["isListing", "selectedCount"]),

  },
  created() {
    this.name = this.selected[0].name
    this.oldName = this.name
  },
  methods: {
    cancel: function () {
      this.$store.commit("closeHovers");
    },

    submit: async function () {


      try {
        buttons.loading("rename-submit");
        await rename({"id": this.selected[0].id, "new_name": this.name});
        this.$toast.success(`${this.oldName} renamed to ${this.name}!`, {
          timeout: 3000,
          position: "bottom-right",
        });

      } catch (e) {

      }
      finally {
        this.$store.commit("setReload", true);
        this.$store.commit("closeHovers");

      }
    },
  },
};
</script>
