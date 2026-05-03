<template>
   <div v-if="progress" class="progress">
      <div :style="{ width: progress + '%' }"></div>
   </div>

   <sidebar></sidebar>

   <main>
      <router-view></router-view>
   </main>

   <upload-files></upload-files>
   <prompts></prompts>
</template>

<script>
import Prompts from "@/components/prompts/Prompts.vue"
import UploadFiles from "../components/prompts/UploadFiles.vue"
import Sidebar from "@/components/sidebar/Sidebar.vue"

import { useMainStore } from "@/stores/mainStore.js"
import { useUploadStore } from "@/stores/uploadStore.js"
import { mapActions, mapState } from "pinia"

import { driver } from "driver.js"
import "driver.js/dist/driver.css"

export default {
   name: "layout",

   components: {
      Sidebar,
      Prompts,
      UploadFiles
   },
   data() {
      return {
         tourClickHandlers: new WeakMap()
      }
   },
   async mounted() {
      // ensure anon state first
      if (!this.isLogged) {
         this.setAnonState()
      }
      if (!this.user.autoSetupComplete && this.isLogged) {
         this.startTour()
      }
   },

   computed: {
      ...mapState(useMainStore, ["isLogged", "user"]),
      ...mapState(useUploadStore, ["progress"])
   },

   methods: {
      ...mapActions(useMainStore, ["setAnonState", "showHover"]),

      nextOnClick(tour, element) {
         const previousHandler = this.tourClickHandlers.get(element)

         if (previousHandler) {
            element.removeEventListener("click", previousHandler)
         }

         const handler = () => {
            element.removeEventListener("click", handler)
            this.tourClickHandlers.delete(element)

            setTimeout(() => {
               tour.moveNext()
            }, 150)
         }

         this.tourClickHandlers.set(element, handler)
         element.addEventListener("click", handler)
      },
      hideButtons() {
         const popover1 = document.querySelector(".driver-popover")
         if (popover1) {
            const prev = popover1.querySelector(".driver-popover-next-btn")
            const close = popover1.querySelector(".driver-popover-prev-btn")

            close.style.display = "none"
            prev.style.display = "none"
         }
      },
      onSkip(tour) {
         let isLastStep = tour.isLastStep()
         let lastStep = tour.getActiveIndex()
         tour.destroy()
         if (isLastStep) return
         this.showHover({
            prompt: "skipOnboarding",
            cancel: () => {
               tour.drive(lastStep)
            }
         })
      },
      // -------------------------
      // main tour
      // -------------------------
      startTour() {
         const tour = driver({
            popoverClass: "driverjs-theme",
            onDestroyStarted: () => this.onSkip(tour),
            onPopoverRender: (popover, { config, state }) => {
               console.log(tour.getActiveStep())
               if (tour.getActiveIndex() === 0) {
                  const firstButton = document.createElement("button");
                  firstButton.innerText = this.$t('tour.buttons.skip');
                  popover.footerButtons.appendChild(firstButton);

                  firstButton.addEventListener("click", () => {
                     this.onSkip(tour)
                  })
               }
               if ([0, 1].includes(tour.getActiveIndex())) {
                  this.hideButtons()
               }
            },
            nextBtnText: this.$t('tour.buttons.next') + " →",
            prevBtnText: "← " + this.$t('tour.buttons.previous'),
         })
         tour.setSteps([
            {
               element: '[data-tour="settings"]',
               popover: {
                  title: this.$t('tour.settings.title'),
                  description: this.$t('tour.settings.description'),
               },
               onHighlightStarted: (element) => {
                  this.nextOnClick(tour, element)
               },
            },
            {
               element: '[data-tour="discord-settings"]',
               popover: {
                  title: this.$t('tour.discordSettings.title'),
                  description: this.$t('tour.discordSettings.description'),
               },
               onHighlightStarted: (element) => {
                  this.nextOnClick(tour, element)
               },
            },
            {
               element: '[data-tour="discord-settings-guild-id"]',
               popover: {
                  title: this.$t('tour.guildId.title'),
                  description: this.$t('tour.guildId.description'),
                  showButtons: ["next"],
               },
            },
            {
               element: '[data-tour="discord-settings-primary-token"]',
               popover: {
                  title: this.$t('tour.primaryToken.title'),
                  description: this.$t('tour.primaryToken.description'),
               },
            },
            {
               element: '[data-tour="discord-settings-attachment-name"]',
               popover: {
                  title: this.$t('tour.attachmentName.title'),
                  description: this.$t('tour.attachmentName.description'),
               },
            },
            {
               element: '[data-tour="discord-settings-auto-setup"]',
               popover: {
                  title: this.$t('tour.autoSetup.title'),
                  description: this.$t('tour.autoSetup.description'),
               },
               onHighlightStarted: (element) => {
                  this.nextOnClick(tour, element)
               },
            }
         ])


         tour.drive()
      }
   }
}
</script>
<style>
.driver-popover {
   background: var(--surfacePrimary);
   border-radius: 6px;
   border: 1px solid #2f3b46;
   box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
   padding: 12px 14px;
   max-width: 260px;
}

.driver-popover-title {
   font-size: 13px;
   font-weight: 600;
   color: var(--textPrimary);
}

.driver-popover-description {
   font-size: 12px;
   line-height: 1.4;
   color: var(--textSecondary);
   padding-top: 1em;
   padding-left: 1em;
}
.driver-popover header {
   height: 2em !important;
}
.driver-popover {
   padding: 5px 6px;
}
.driver-popover-navigation-btns button {
   margin-bottom: 0.5em;
}

</style>