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
import {mapGetters, mapMutations, mapState} from "vuex";
import {moveToTrash, remove} from "@/api/item.js";

export default {
  name: "delete",
  computed: {
    ...mapGetters(["selectedCount", "currentPrompt"]),
    ...mapState(["selected", "items"]),
  },
  created() {
    // Save the event listener function to a property
    this.keyEvent = (event) => { // fucking spent 3 hours debuging this fucking piece of code fuck you java script, retarded language istg
      // Enter
      if (event.keyCode === 13) {
        console.log("calling submit from event listener");
        this.submit();
      }
    };

    // Add the event listener using the saved function
    window.addEventListener("keydown", this.keyEvent);
  },

  beforeDestroy() {
    // Remove the event listener using the saved function
    window.removeEventListener("keydown", this.keyEvent);
  },



  methods: {
    ...mapMutations(["closeHover", "resetSelected"]),
    submit: async function () {
      try {
        let ids = this.selected.map(item => item.id);

        let res = await remove({"ids": ids});

        let updatedItem = this.items.filter(item => !ids.includes(item.id));

        this.$store.commit("setItems", updatedItem);
        let message = this.$t('toasts.itemMovedToTrash', {amount: ids.length})
        console.log(message)
        this.$toast.success(message, {
          id: res.task_id,
          timeout: null
        });
        this.currentPrompt?.confirm();

      } catch (error) {
        console.log(error)
        //nothing has to be done
      }
      finally {
        this.resetSelected()
        this.closeHover()
        //this.$store.commit("setReload", true);


      }
    },
  },
};
</script>
