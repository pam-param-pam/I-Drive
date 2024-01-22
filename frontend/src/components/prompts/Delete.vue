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
    ...mapMutations(["closeHovers", "resetSelected"]),
    submit: async function () {
      console.log("SUMBIT CALLED WITH" + JSON.stringify(this.selected))
      try {

        let ids = this.selected.map(item => item.id);
        let updatedItem = this.items.filter(item => !ids.includes(item.id));
        this.$store.commit("setItems", updatedItem);

        console.log("seleted are: " + ids)

        console.log("seleted ids are: " + JSON.stringify(this.selected))
        this.$store.commit("resetSelected", {});



          let res = await remove({"ids": ids});
          console.log("res: " + JSON.stringify(res))
          let message = `Deleting ${ids.length} items...`


          console.log("showing toast")

          let id = this.$toast.info(message, {
            id: res.task_id,
            timeout: 0,
            draggable: false,
            closeOnClick: false,
            position: "bottom-right",
          });
          console.log("showing toast1")

          console.log("toast's id is: " + id)



      } catch (e) {
        console.log(e)
        //nothing has to be done
      }
      finally {
        this.closeHovers()
        //this.$store.commit("setReload", true);


      }
    },
  },
};
</script>
