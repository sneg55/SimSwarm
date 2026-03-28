<template>
  <div class="relative">
    <router-link
      :to="linkTo"
      class="block bg-gradient-to-b from-ocean-abyss to-ocean-deep border border-mist-depth rounded-xl
             px-6 py-5 pr-14 relative overflow-hidden cursor-pointer group
             transition-all duration-350 ease-spring
             hover:-translate-y-0.5 hover:border-ocean-teal hover:shadow-[0_8px_32px_rgba(14,116,144,0.1)]"
    >
      <div
        class="absolute top-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-400"
        :style="{ background: `linear-gradient(90deg, transparent, ${statusColor}, transparent)` }"
      />

      <div class="flex items-center justify-between mb-2">
        <h3 class="text-base font-semibold text-mist-foam transition-colors group-hover:text-ocean-glow truncate mr-4">
          {{ job.goal || 'Simulation' }}
        </h3>
        <div class="flex items-center gap-3 flex-shrink-0">
          <span class="text-sm font-semibold text-ocean-glow opacity-0 group-hover:opacity-100 transition-opacity">
            {{ actionLabel }} &rarr;
          </span>
          <span
            class="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border"
            :style="{
              color: statusColor,
              background: statusColor + '18',
              borderColor: statusColor + '33',
            }"
          >
            <span
              class="w-[7px] h-[7px] rounded-full"
              :class="isRunning ? 'animate-[breathe_2.5s_ease-in-out_infinite]' : ''"
              :style="{ background: statusColor }"
            />
            {{ statusLabel }}
          </span>
        </div>
      </div>

      <div v-if="job.key_insight && job.status === 'COMPLETED'" class="flex items-start gap-2.5 mb-3 px-3 py-2 bg-ocean-deep/60 rounded-lg border border-mist-depth">
        <span class="w-[3px] min-h-[18px] rounded-sm flex-shrink-0 mt-0.5" :style="{ background: insightColor }" />
        <span class="text-sm text-mist leading-snug">{{ job.key_insight }}</span>
      </div>
      <div v-else-if="job.status === 'FAILED' && job.error_message" class="text-sm text-mist-slate mb-3">
        {{ job.error_message }}
      </div>

      <div class="flex gap-4 font-mono text-xs text-mist-slate transition-colors group-hover:text-mist-drift">
        <span>{{ job.tier }} tier</span>
        <span>&middot;</span>
        <span v-if="isRunning && job.pipeline_stage">Step {{ job.pipeline_stage }}/5</span>
        <span v-else-if="job.pipeline_seconds">{{ formatDuration(job.pipeline_seconds) }}</span>
        <span v-if="isRunning && job.pipeline_stage">&middot;</span>
        <span>{{ formatTime(job.created_at) }}</span>
      </div>
    </router-link>

    <!-- Kebab menu -->
    <div class="absolute top-4 right-4 z-10" ref="menuRef">
      <button
        @click.prevent.stop="menuOpen = !menuOpen"
        class="w-8 h-8 flex items-center justify-center rounded-lg text-mist-slate hover:text-mist-foam hover:bg-ocean-teal/15 transition-all"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="5" r="2" />
          <circle cx="12" cy="12" r="2" />
          <circle cx="12" cy="19" r="2" />
        </svg>
      </button>
      <div
        v-if="menuOpen"
        class="absolute right-0 top-full mt-1 bg-ocean-deep border border-mist-depth rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.4)] overflow-hidden min-w-[140px] z-20"
      >
        <button
          @click.prevent.stop="handleDelete"
          class="w-full text-left px-4 py-2.5 text-sm text-coral hover:bg-coral/10 transition-colors flex items-center gap-2"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          Delete
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  job: { type: Object, required: true },
})

const emit = defineEmits(['delete'])

const menuOpen = ref(false)
const menuRef = ref(null)

const STATUS_COLORS = {
  COMPLETED: '#22D3EE',
  RUNNING: '#A78BFA',
  PROVISIONING: '#A78BFA',
  PENDING: '#64748B',
  FAILED: '#FF6B6B',
  REFUNDED: '#FBBF24',
}

const STATUS_LABELS = {
  COMPLETED: 'Completed',
  RUNNING: 'Running',
  PROVISIONING: 'Provisioning',
  PENDING: 'Pending',
  FAILED: 'Failed',
  REFUNDED: 'Refunded',
}

const statusColor = computed(() => STATUS_COLORS[props.job.status] || '#64748B')
const statusLabel = computed(() => STATUS_LABELS[props.job.status] || props.job.status)
const isRunning = computed(() => ['RUNNING', 'PROVISIONING'].includes(props.job.status))

const linkTo = computed(() => {
  if (props.job.status === 'COMPLETED') return `/sim/${props.job.id}/results`
  return `/sim/${props.job.id}`
})

const actionLabel = computed(() => {
  if (props.job.status === 'COMPLETED') return 'View results'
  if (isRunning.value) return 'View progress'
  if (props.job.status === 'FAILED') return 'View details'
  return 'View'
})

const insightColor = computed(() => {
  const text = (props.job.key_insight || '').toLowerCase()
  if (text.match(/drop|decline|negative|fell|crash|risk|crisis|fail/)) return '#FF6B6B'
  if (text.match(/positive|grow|recovery|bull|increase|strong|rise/)) return '#6EE7B7'
  return '#FBBF24'
})

function handleDelete() {
  menuOpen.value = false
  emit('delete', props.job.id)
}

function onClickOutside(e) {
  if (menuRef.value && !menuRef.value.contains(e.target)) {
    menuOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))

function formatDuration(seconds) {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHrs = Math.floor(diffMin / 60)
  if (diffHrs < 24) return `${diffHrs} hour${diffHrs > 1 ? 's' : ''} ago`
  const diffDays = Math.floor(diffHrs / 24)
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
@keyframes breathe {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}
</style>
