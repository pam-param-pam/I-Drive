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
        @keyup.enter="submit()"

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
        @click="submit()"
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
import {mapState} from "vuex"
import {rename} from "@/api/item.js"

export default {
  name: "rename",
  data() {
    return {
      name: "",
      oldName: "",
    }
  },

  computed: {
    ...mapState(["selected"]),

  },
  created() {
    this.name = this.selected[0].name
    this.oldName = this.name
  },
  methods: {

    submit: async function () {

      try {
        let id = this.selected[0].id
        let new_name = this.name
        await rename({"id": id, "new_name": new_name})

        //this.$store.commit("renameItem", {id: id, newName: new_name})

        let message = this.$t('toasts.itemRenamed')
        this.$toast.success(message)

      }  finally {
        this.$store.commit("closeHover")

      }
    },
  },
}
</script>
