<template>
  <div class="max-w-[640px] mx-auto px-4 pt-20 pb-16">
    <router-link to="/dashboard" class="text-sm text-mist-slate hover:text-ocean-glow transition-colors">&larr; Back to Dashboard</router-link>

    <div v-if="loading" class="text-center py-20 text-mist-slate">Loading...</div>

    <div v-else-if="job" class="mt-6 space-y-6">

      <!-- Header -->
      <div class="text-center">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold mb-4" :class="statusBadgeClass">
          <span class="w-2 h-2 rounded-full" :class="statusDotClass" />
          {{ statusLabel }}
        </div>
        <h1 class="text-2xl font-bold text-mist-foam tracking-tight">{{ job.goal }}</h1>
        <p class="text-sm text-mist-slate mt-1 capitalize">{{ job.tier }} tier</p>
      </div>

      <!-- Pipeline Progress -->
      <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-6">
        <PipelineProgress
          :current-step="currentStep"
          :completed-steps="completedSteps"
        />

        <!-- Status details -->
        <div class="mt-5 pt-5 border-t border-mist-depth">
          <!-- Running state -->
          <template v-if="isActive">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-mist-drift">Current stage</span>
              <span class="text-sm font-semibold text-mist-foam">{{ currentStageName }}</span>
            </div>
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-mist-drift">Progress</span>
              <span class="font-mono text-sm text-ocean-glow">{{ job.pipeline_stage || 0 }} / 5 stages</span>
            </div>
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-mist-drift">Elapsed time</span>
              <span class="font-mono text-sm text-mist-foam">{{ elapsed }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Estimated remaining</span>
              <span class="font-mono text-sm text-mist-foam">{{ eta }}</span>
            </div>
          </template>

          <!-- Pending state -->
          <template v-else-if="job.status === 'PENDING'">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-mist-drift">Status</span>
              <span class="text-sm text-mist-foam">Waiting for GPU allocation</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Estimated wait</span>
              <span class="font-mono text-sm text-mist-foam">1–3 minutes</span>
            </div>
          </template>

          <!-- Completed -->
          <template v-else-if="job.status === 'COMPLETED'">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-mist-drift">Duration</span>
              <span class="font-mono text-sm text-organic-seafoam">{{ formatDuration(job.pipeline_seconds) }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Completed</span>
              <span class="text-sm text-mist-foam">{{ formatDate(job.completed_at) }}</span>
            </div>
          </template>
        </div>
      </div>

      <!-- Email notification banner -->
      <div v-if="isActive || job.status === 'PENDING'" class="flex items-center gap-3 px-5 py-3.5 rounded-xl bg-ocean-cyan/8 border border-ocean-cyan/15 text-ocean-glow text-sm">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="flex-shrink-0">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
          <polyline points="22,6 12,13 2,6"/>
        </svg>
        We'll email you when your simulation is ready. You can close this page.
      </div>

      <!-- Completed CTA -->
      <div v-if="job.status === 'COMPLETED'" class="text-center py-4">
        <router-link
          :to="`/sim/${jobId}/results`"
          class="inline-flex items-center gap-2 px-8 py-3 rounded-xl text-base font-bold text-white
                 bg-gradient-to-br from-ocean-cyan to-cyan-500
                 glow-cyan transition-all ease-spring
                 hover:glow-cyan-lg hover:-translate-y-0.5"
        >
          View Results
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        </router-link>
      </div>

      <!-- Failed state -->
      <div v-if="job.status === 'FAILED'" class="bg-coral/8 border border-coral/20 rounded-2xl p-5">
        <div class="flex items-center gap-2 text-coral font-semibold mb-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          Simulation failed
        </div>
        <p class="text-sm text-mist-drift">{{ job.error_message || 'An unexpected error occurred. Your credits have been refunded.' }}</p>
        <router-link to="/sim/new" class="inline-block mt-3 text-sm text-ocean-glow hover:underline">Try again &rarr;</router-link>
      </div>

      <!-- Live chat replay -->
      <div v-if="chatMessages.length > 0">
        <ChatReplay :messages="chatMessages" :start-expanded="isActive" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import PipelineProgress from '../components/PipelineProgress.vue'
import ChatReplay from '../components/ChatReplay.vue'
import { getJob } from '../api/jobs.js'

const STAGE_NAMES = ['Seeding', 'Researching', 'Simulating', 'Analyzing', 'Generating report']
const STAGE_STEP_IDS = ['seed', 'research', 'prepare', 'simulate', 'report']

// Estimated seconds per stage by tier
const TIER_ESTIMATES = {
  small: [30, 60, 300, 120, 60],     // ~10 min total
  medium: [30, 120, 900, 300, 120],   // ~25 min total
  large: [60, 300, 3600, 900, 300],   // ~1.5 hr total
}

const route = useRoute()
const jobId = route.params.id

const job = ref(null)
const loading = ref(true)
const now = ref(Date.now())
let pollInterval = null
let tickInterval = null

const isActive = computed(() =>
  job.value && ['RUNNING', 'PROVISIONING'].includes(job.value.status)
)

const currentStep = computed(() => {
  if (!job.value || !job.value.pipeline_stage) return null
  return STAGE_STEP_IDS[job.value.pipeline_stage - 1] ?? null
})

const completedSteps = computed(() => {
  if (!job.value || !job.value.pipeline_stage) return []
  return STAGE_STEP_IDS.slice(0, job.value.pipeline_stage - 1)
})

const currentStageName = computed(() => {
  if (!job.value || !job.value.pipeline_stage) return 'Preparing...'
  return STAGE_NAMES[job.value.pipeline_stage - 1] || 'Processing'
})

const elapsed = computed(() => {
  if (!job.value || !job.value.created_at) return '--'
  const start = new Date(job.value.created_at).getTime()
  const diff = Math.floor((now.value - start) / 1000)
  return formatSeconds(diff)
})

const eta = computed(() => {
  if (!job.value || !job.value.pipeline_stage || !job.value.tier) return '--'
  const estimates = TIER_ESTIMATES[job.value.tier] || TIER_ESTIMATES.medium
  // Sum remaining stages
  const remaining = estimates.slice(job.value.pipeline_stage - 1).reduce((a, b) => a + b, 0)
  if (remaining < 60) return '< 1 min'
  return formatSeconds(remaining)
})

const chatMessages = computed(() => {
  if (!job.value) return []
  try {
    const raw = job.value.result_chat_log || '[]'
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return Array.isArray(parsed) ? parsed : []
  } catch { return [] }
})

const statusLabel = computed(() => {
  const map = {
    COMPLETED: 'Complete',
    RUNNING: 'Running',
    PROVISIONING: 'Provisioning GPU',
    PENDING: 'Pending',
    FAILED: 'Failed',
    REFUNDED: 'Refunded',
  }
  return map[job.value?.status] || job.value?.status || ''
})

const statusBadgeClass = computed(() => {
  const map = {
    COMPLETED: 'bg-ocean-glow/10 text-ocean-glow border border-ocean-glow/20',
    RUNNING: 'bg-organic-violet/10 text-organic-violet border border-organic-violet/20',
    PROVISIONING: 'bg-organic-violet/10 text-organic-violet border border-organic-violet/20',
    PENDING: 'bg-mist-slate/10 text-mist-slate border border-mist-slate/20',
    FAILED: 'bg-coral/10 text-coral border border-coral/20',
  }
  return map[job.value?.status] || 'bg-mist-depth text-mist-slate'
})

const statusDotClass = computed(() => {
  if (isActive.value || job.value?.status === 'PROVISIONING') return 'bg-organic-violet animate-[breathe_2.5s_ease-in-out_infinite]'
  if (job.value?.status === 'PENDING') return 'bg-mist-slate animate-[breathe_3s_ease-in-out_infinite]'
  if (job.value?.status === 'COMPLETED') return 'bg-ocean-glow'
  if (job.value?.status === 'FAILED') return 'bg-coral'
  return 'bg-mist-slate'
})

function formatSeconds(s) {
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

function formatDuration(seconds) {
  if (!seconds) return '--'
  return formatSeconds(seconds)
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

async function fetchJob() {
  try {
    job.value = await getJob(jobId)
    if (job.value.status === 'COMPLETED' || job.value.status === 'FAILED') {
      clearInterval(pollInterval)
    }
  } catch (err) {
    console.error('Failed to fetch job:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchJob()
  pollInterval = setInterval(fetchJob, 3000)
  tickInterval = setInterval(() => { now.value = Date.now() }, 1000)
})

onUnmounted(() => {
  clearInterval(pollInterval)
  clearInterval(tickInterval)
})
</script>

<style scoped>
@keyframes breathe {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}
</style>
