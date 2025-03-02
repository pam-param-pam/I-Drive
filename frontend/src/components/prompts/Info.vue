<template>
   <div class="card floating">
      <div class="card-title">
         <h2>{{ $t('prompts.itemInfo') }}</h2>
      </div>

      <div class="card-content">
         <p v-if="selected.length > 1">
            {{ $t('prompts.itemsSelected', { count: selected.length }) }}
         </p>

         <p v-if="name" class="break-word">
            <strong>{{ $t('prompts.displayName') }}:</strong> {{ name }}
         </p>

         <p v-if="id" class="break-word">
            <strong>{{ $t('prompts.identifier') }}:</strong> {{ id }}
         </p>
         <p v-if="inTrashSince">
            <strong>{{ $t('prompts.inTrashSince') }}:</strong> {{ humanTime(inTrashSince) }}
         </p>
         <p v-if="type">
            <strong>{{ $t('prompts.type') }}:</strong> {{ type }}
         </p>

         <p v-if="extension">
            <strong>{{ $t('prompts.extension') }}:</strong> {{ extension }}
         </p>

         <p v-if="size">
            <strong>{{ $t('prompts.size') }}: </strong>
            <code>
               <a @dblclick="changeView($event, 'size')">{{ humanSize(size) }}</a>
            </code>
         </p>

         <p v-if="encryptionMethod">
            <strong>{{ $t('settings.encryptionMethod') }}:</strong> {{ $t(encryptionMethod) }}
            <span v-if="is_encrypted" class="checkmark-true"></span>
            <span v-else class="checkmark-false"></span>
         </p>

         <p v-if="owner">
            <strong>{{ $t('prompts.owner') }}:</strong> {{ owner }}
         </p>

         <div v-if="resolution">
            <strong>{{ $t('prompts.resolution') }}:</strong>
            {{ resolution.width }} x {{ resolution.height }}
         </div>
         <div v-if="duration">
            <strong>{{ $t('prompts.duration') }}:</strong> {{ formatSeconds(duration) }}
         </div>
         <p v-if="created">
            <strong>{{ $t('prompts.created') }}:</strong> {{ humanTime(created) }}
         </p>
         <p v-if="last_modified">
            <strong>{{ $t('prompts.lastModified') }}:</strong> {{ humanTime(last_modified) }}
         </p>
         <p v-if="iso">
            <strong>{{ $t('prompts.iso') }}:</strong> {{ iso }}
         </p>
         <p v-if="aperture">
            <strong>{{ $t('prompts.aperture') }}:</strong> f/{{ aperture }}
         </p>
         <p v-if="exposureTime">
            <strong>{{ $t('prompts.exposureTime') }}:</strong> {{ exposureTime }} sec
         </p>
         <p v-if="focalLength">
            <strong>{{ $t('prompts.focalLength') }}:</strong> {{ focalLength }}mm
         </p>
         <p v-if="modelName">
            <strong>{{ $t('prompts.modelName') }}:</strong> {{ modelName }}
         </p>

         <!-- Expandable section -->
         <div v-if="isDir" class="expandable-section">
            <div class="expandable-header" @click="fetchAdditionalInfo">
               <strong>{{ $t('prompts.fetchMoreInfo') }}</strong>
               <i :class="{ expanded: isExpanded }" class="material-icons expand-icon">
                  keyboard_arrow_down
               </i>
            </div>

            <div v-if="isExpanded" class="expandable-content">
               <p>
                  <strong>{{ $t('prompts.numberDirs') }}:</strong> {{ numberDirs }}
               </p>
               <p>
                  <strong>{{ $t('prompts.numberFiles') }}:</strong> {{ numberFiles }}
               </p>
               <p>
                  <strong>{{ $t('prompts.size') }}: </strong>
                  <code>
                     <a v-if="!isMoreDataFetched" @dblclick="changeView($event, 'folderSize')">{{
                        humanSize(0)
                     }}</a>
                     <a v-else @dblclick="changeView($event, 'folderSize')">{{
                        humanSize(folderSize)
                     }}</a>
                  </code>
               </p>
            </div>
         </div>
      </div>

      <div class="card-action">
         <button
            :aria-label="$t('buttons.ok')"
            :title="$t('buttons.ok')"
            class="button button--flat"
            type="submit"
            @click="closeHover()"
         >
            {{ $t('buttons.ok') }}
         </button>
      </div>
   </div>
</template>

<script>
import { filesize } from '@/utils'
import moment from 'moment/min/moment-with-locales.js'
import { fetchAdditionalInfo } from '@/api/folder.js'
import { useMainStore } from '@/stores/mainStore.js'
import { mapActions, mapState } from 'pinia'
import { encryptionMethod, encryptionMethods } from '@/utils/constants.js'
import { formatSeconds } from '@/utils/common.js'

export default {
   name: 'info',

   data() {
      return {
         numberDirs: 'Loading...',
         numberFiles: 'Loading...',
         folderSize: 'Loading...',
         isExpanded: false
      }
   },

   computed: {
      ...mapState(useMainStore, ['selected', 'settings', 'currentFolder', 'selectedCount']),
      isMoreDataFetched() {
         return this.folderSize !== 'Loading...'
      },
      size() {
         if (this.selectedCount >= 1) {
            let sum = 0
            for (let selected of this.selected) {
               if (!selected.isDir) sum += selected.size
            }
            return sum
         }
         return null
      },

      name() {
         if (this.selectedCount === 0) {
            return this.currentFolder.name
         } else if (this.selectedCount === 1) {
            return this.selected[0].name
         }
         return null
      },

      resolution() {
         //todo
         return null
      },
      encryptionMethod() {
         if (this.selectedCount === 1) {
            if (this.selected[0].isDir) return null
            return encryptionMethods[this.selected[0].encryption_method]
         }
         return null
      },
      created() {
         if (this.selectedCount === 0) {
            return this.currentFolder.created
         } else if (this.selectedCount === 1) {
            return this.selected[0].created
         }
         return null
      },
      last_modified() {
         if (this.selectedCount === 0) {
            return this.currentFolder.last_modified
         } else if (this.selectedCount === 1) {
            return this.selected[0].last_modified
         }
         return null
      },
      id() {
         if (this.selectedCount === 0) {
            return this.currentFolder.id
         } else if (this.selectedCount === 1) {
            return this.selected[0].id
         }
         return null
      },
      ready() {
         if (this.selectedCount === 1) {
            return this.selected[0].ready
         }
         return null
      },

      is_encrypted() {
         if (this.selectedCount === 1) {
            if (this.selected[0].isDir) return null
            return this.selected[0].encryption_method !== encryptionMethod.NotEncrypted
         }
         return null
      },
      type() {
         if (this.selectedCount === 1) {
            return this.selected[0].type
         }
         return null
      },
      iso() {
         if (this.selectedCount === 1) {
            return this.selected[0].iso
         }
         return null
      },
      exposureTime() {
         if (this.selectedCount === 1) {
            return this.selected[0].exposure_time
         }
         return null
      },
      aperture() {
         if (this.selectedCount === 1) {
            return this.selected[0].aperture
         }
         return null
      },
      focalLength() {
         if (this.selectedCount === 1) {
            return this.selected[0].focal_length
         }
         return null
      },
      modelName() {
         if (this.selectedCount === 1) {
            return this.selected[0].model_name
         }
         return null
      },
      extension() {
         if (this.selectedCount === 1) {
            let extension = this.selected[0].extension
            if (extension) return extension.replace('.', '')
         }
         return null
      },
      inTrashSince() {
         if (this.selectedCount === 0) {
            return this.currentFolder.in_trash_since
         } else if (this.selectedCount === 1) {
            return this.selected[0].in_trash_since
         }
         return null
      },
      duration() {
         if (this.selectedCount === 1) {
            return this.selected[0].duration
         }
         return null
      },
      owner() {
         if (this.selectedCount === 0) {
            return this.currentFolder.owner
         } else if (this.selectedCount === 1) {
            return this.selected[0].owner
         }
         return null
      },
      isDir() {
         if (this.selectedCount === 0) {
            return this.currentFolder.isDir
         }
         if (this.selectedCount === 1) {
            return this.selected[0].isDir
         }

         return false
      }
   },

   methods: {
      formatSeconds,

      ...mapActions(useMainStore, ['closeHover']),

      async fetchAdditionalInfo() {
         // we want to fetch data only once
         if (this.isMoreDataFetched) {
            this.isExpanded = !this.isExpanded
            return
         }

         let folder
         if (this.selectedCount === 0) folder = this.currentFolder
         else if (this.selected[0].isDir) folder = this.selected[0]

         if (folder) {
            let res = await fetchAdditionalInfo(folder.id)
            this.folderSize = res.folder_size
            this.numberDirs = res.folder_count
            this.numberFiles = res.file_count
            this.isExpanded = !this.isExpanded
         }
      },

      humanSize(size) {
         return filesize(size)
      },

      humanTime(date) {
         if (this.settings.dateFormat) {
            return moment(date, 'YYYY-MM-DD HH:mm').format('DD/MM/YYYY, hh:mm')
         }
         //todo czm globalny local nie dzIała?
         let locale = this.settings?.locale || 'en'

         moment.locale(locale)
         // Parse the target date
         return moment(date, 'YYYY-MM-DD HH:mm').endOf('second').fromNow()
      },

      async changeView(event, type) {
         if (event.target.innerHTML.toString().includes('bytes')) {
            if (type === 'size') {
               event.target.innerHTML = this.humanSize(this.size)
            } else if (type === 'folderSize') {
               event.target.innerHTML = this.humanSize(this.folderSize)
            }
         } else {
            if (type === 'size') {
               event.target.innerHTML = this.size + ' bytes'
            } else if (type === 'folderSize') {
               event.target.innerHTML = this.folderSize + ' bytes'
            }
         }
         if (type === 'size') {
            navigator.clipboard.writeText(this.size)
         }
         else if (type === 'folderSize') {
            navigator.clipboard.writeText(this.folderSize)
         }
         this.$toast.success(this.$t('toasts.copied'))

      }
   }
}
</script>
<style lang="css" scoped>
.checkmark-true:after {
   content: '\002705';
   color: #2ecc71;
   margin-left: 5px;
}

.checkmark-false:after {
   content: '\00274C';
   color: #d31010;
   margin-left: 5px;
}
</style>
