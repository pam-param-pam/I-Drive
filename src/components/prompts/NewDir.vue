<template>
  <div class="card floating">
    <div class="card-title">
      <h2>{{ $t("prompts.newDir") }}</h2>
    </div>

    <div class="card-content">
      <p>{{ $t("prompts.newDirMessage") }}</p>
      <input

        ref="input"
        class="input input--block"
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
        :disabled="!canSubmit"
        :aria-label="$t('buttons.create')"
        id="create-button"
        :title="$t('buttons.create')"
        @click="submit"
      >
        {{ $t("buttons.create") }}
      </button>
    </div>
  </div>
</template>

<script>
import {mapState} from "vuex"
import {create} from "@/api/folder.js"
import Action from "@/components/header/Action.vue"

export default {
  name: "new-dir",
  components: {Action},
  data() {
    return {
      name: "",
    }
  },
  computed: {
    ...mapState(["currentFolder"]),
    canSubmit() {
      return this.name.length > 0
    }
  },
  
  methods: {
    async submit(event) {

      if (this.canSubmit) {
        try {

          await create({"parent_id": this.currentFolder?.id, "name": this.name})
          let message = this.$t('toasts.folderCreated', { name: this.name})
          this.$toast.success(message)

        }
        finally {
          this.$store.commit("closeHover")
        }
      }
    },
  },
}
</script>
