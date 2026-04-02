<template>
  <div class="max-w-[640px] mx-auto px-4 pt-20 pb-16">
    <router-link to="/dashboard" class="text-sm text-mist-slate hover:text-ocean-glow transition-colors">&larr; Back to Dashboard</router-link>

    <div v-if="loading" class="space-y-6 mt-6">
      <SkeletonCard :lines="0" />
      <SkeletonCard :lines="3" />
    </div>

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

        <!-- Overall progress bar (running/provisioning) -->
        <div v-if="isActive" class="mt-5">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-semibold text-mist-drift">{{ currentStageName }}...</span>
            <span class="font-mono text-xs text-ocean-glow">{{ progressPercent }}%</span>
          </div>
          <div class="h-1.5 bg-ocean-abyss rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-[width] duration-1000 ease-smooth relative"
              :style="{ width: progressPercent + '%', background: 'linear-gradient(90deg, #0E7490, #22D3EE)' }"
            >
              <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
            </div>
          </div>
        </div>

        <!-- Status details -->
        <div class="mt-5 pt-5 border-t border-mist-depth space-y-3">
          <!-- Running state -->
          <template v-if="isActive">
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Stage</span>
              <span class="text-sm font-semibold text-mist-foam">
                {{ job.pipeline_stage || 0 }} of 5
                <span class="text-mist-slate font-normal ml-1">— {{ currentStageName }}</span>
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Elapsed</span>
              <span class="font-mono text-sm text-mist-foam tabular-nums">{{ elapsed }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Estimated remaining</span>
              <span class="font-mono text-sm text-ocean-glow tabular-nums">{{ eta }}</span>
            </div>
            <div v-if="liveRound !== null && job.pipeline_stage === 3 && !isLiveStale"
              class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Rounds</span>
              <span class="font-mono text-sm text-mist-foam tabular-nums">
                {{ liveRound }} <span class="text-mist-slate font-normal">/ {{ liveMaxRounds || '--' }}</span>
              </span>
            </div>
          </template>

          <!-- Pending state -->
          <template v-else-if="job.status === 'PENDING' || job.status === 'PROVISIONING'">
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Status</span>
              <span class="text-sm text-mist-foam flex items-center gap-2">
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-organic-violet animate-[breathe_2s_ease-in-out_infinite]" />
                {{ job.status === 'PROVISIONING' ? 'Allocating GPU...' : 'Waiting for GPU resources' }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Elapsed</span>
              <span class="font-mono text-sm text-mist-foam tabular-nums">{{ elapsed }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Estimated total</span>
              <span class="font-mono text-sm text-mist-slate">{{ estimatedTotal }}</span>
            </div>
          </template>

          <!-- Completed -->
          <template v-else-if="job.status === 'COMPLETED'">
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Duration</span>
              <span class="font-mono text-sm text-mist-foam">{{ completedDuration }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Completed</span>
              <span class="text-sm text-mist-foam">{{ formatDate(job.completed_at) }}</span>
            </div>
          </template>
        </div>
      </div>

      <!-- Live Activity feed (log lines + partial chat during run) -->
      <LiveActivity
        v-if="showLiveActivity"
        :log-lines="liveLogLines"
        :partial-chat="livePartialChat"
        :stage="job.pipeline_stage || 0"
      />

      <!-- Email notification banner -->
      <div v-if="isActive || job.status === 'PENDING'" class="flex items-center gap-3 px-5 py-3.5 rounded-xl bg-ocean-cyan/8 border border-ocean-cyan/15 text-ocean-glow text-sm">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="flex-shrink-0">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
          <polyline points="22,6 12,13 2,6"/>
        </svg>
        We'll email you when your simulation is ready. You can close this page.
      </div>

      <!-- Web research card -->
      <div v-if="job.enriched_seed" class="bg-ocean-deep border border-mist-depth rounded-2xl overflow-hidden">
        <button @click="researchOpen = !researchOpen"
          class="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-ocean-teal/5 transition-colors">
          <span class="text-sm font-semibold text-ocean-glow flex items-center gap-2">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            Web Research
          </span>
          <svg class="w-4 h-4 text-mist-slate transition-transform" :class="{ 'rotate-180': researchOpen }" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div v-show="researchOpen" class="px-5 pb-4">
          <ReportViewer :content="job.enriched_seed" />
        </div>
      </div>

      <!-- Web research unavailable notice (show only after 30s grace period for enrichment to complete) -->
      <div v-else-if="job.enrich_web && !job.enriched_seed && (isActive || job.status === 'PENDING') && elapsedSeconds > 30"
           class="flex items-center gap-3 px-5 py-3 rounded-xl bg-organic-violet/5 border border-organic-violet/15 text-sm text-mist-drift">
        Web research unavailable — running with your original seed
        <button @click="retryEnrich" :disabled="enrichRetrying"
          class="text-ocean-glow hover:underline text-xs ml-auto disabled:opacity-50">
          {{ enrichRetrying ? 'Retrying...' : 'Retry' }}
        </button>
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
        <button
          @click="handleRetry"
          :disabled="retrying"
          class="inline-block mt-3 text-sm text-ocean-glow hover:underline disabled:opacity-50 disabled:cursor-wait"
        >{{ retrying ? 'Retrying...' : 'Retry this simulation' }} &rarr;</button>
      </div>

      <!-- Live chat replay (only while running, not after completion) -->
      <div v-if="isActive && chatMessages.length > 0">
        <ChatReplay :messages="chatMessages" :start-expanded="true" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PipelineProgress from '../components/PipelineProgress.vue'
import ChatReplay from '../components/ChatReplay.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ReportViewer from '../components/ReportViewer.vue'
import LiveActivity from '../components/LiveActivity.vue'
import { getJob, retryJob, retryEnrichment } from '../api/jobs.js'

const STAGE_NAMES = ['Seeding', 'Researching', 'Simulating', 'Analyzing', 'Generating report']
const STAGE_STEP_IDS = ['seed', 'research', 'simulate', 'analyze', 'report']

// Estimated seconds per stage by tier
const TIER_ESTIMATES = {
  small: [30, 60, 300, 120, 60],     // ~10 min total
  medium: [30, 120, 900, 300, 120],   // ~25 min total
  large: [60, 300, 3600, 900, 300],   // ~1.5 hr total
}

const route = useRoute()
const router = useRouter()
const jobId = route.params.id

const job = ref(null)
const loading = ref(true)
const retrying = ref(false)
const now = ref(Date.now())
const researchOpen = ref(false)
const enrichRetrying = ref(false)
let pollInterval = null
let tickInterval = null

// Citations are rendered inline via markdown links in ReportViewer
const citations = computed(() => {
  if (!job.value?.enrichment_citations) return []
  try { return JSON.parse(job.value.enrichment_citations) } catch { return [] }
})

async function retryEnrich() {
  enrichRetrying.value = true
  try {
    await retryEnrichment(jobId)
  } catch { /* ignore */ }
  enrichRetrying.value = false
}

const isActive = computed(() =>
  job.value && ['RUNNING', 'PROVISIONING'].includes(job.value.status)
)

const currentStep = computed(() => {
  if (!job.value) return null
  if (job.value.status === 'COMPLETED') return null
  if (job.value.status === 'FAILED') return null
  // PENDING/PROVISIONING = seed is done, research is waiting
  if (['PENDING', 'PROVISIONING'].includes(job.value.status)) return 'research'
  if (!job.value.pipeline_stage) return 'research'
  return STAGE_STEP_IDS[job.value.pipeline_stage - 1] ?? null
})

const completedSteps = computed(() => {
  if (!job.value) return []
  if (job.value.status === 'COMPLETED') return [...STAGE_STEP_IDS]
  // PENDING/PROVISIONING = seed is done (user already uploaded the document)
  if (['PENDING', 'PROVISIONING'].includes(job.value.status)) return ['seed']
  if (!job.value.pipeline_stage) return ['seed']
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

const estimatedTotalSeconds = computed(() => {
  if (!job.value || !job.value.tier) return 0
  const estimates = TIER_ESTIMATES[job.value.tier] || TIER_ESTIMATES.medium
  return estimates.reduce((a, b) => a + b, 0)
})

const estimatedTotal = computed(() => {
  const total = estimatedTotalSeconds.value
  if (!total) return '--'
  return '~' + formatSeconds(total)
})

const elapsedSeconds = computed(() => {
  if (!job.value || !job.value.created_at) return 0
  return Math.floor((now.value - new Date(job.value.created_at).getTime()) / 1000)
})

const progressPercent = computed(() => {
  if (!job.value || !job.value.pipeline_stage) return 0
  // Each stage is 20% of total, current stage partially complete based on time
  const stageBase = (job.value.pipeline_stage - 1) * 20
  const estimates = TIER_ESTIMATES[job.value.tier] || TIER_ESTIMATES.medium
  const currentEstimate = estimates[job.value.pipeline_stage - 1] || 300
  const elapsedInStage = elapsedSeconds.value - estimates.slice(0, job.value.pipeline_stage - 1).reduce((a, b) => a + b, 0)
  const stageProgress = Math.min(0.95, Math.max(0, elapsedInStage / currentEstimate))
  return Math.min(99, Math.round(stageBase + stageProgress * 20))
})

const eta = computed(() => {
  if (!job.value || !job.value.pipeline_stage || !job.value.tier) return '--'
  const total = estimatedTotalSeconds.value
  const el = elapsedSeconds.value
  if (el <= 0 || total <= 0) return '--'
  // Estimate remaining based on progress ratio
  const pct = progressPercent.value / 100
  if (pct <= 0.01) return '~' + formatSeconds(total)
  const estimatedRemaining = Math.max(0, Math.round((el / pct) * (1 - pct)))
  if (estimatedRemaining < 30) return '< 1 min'
  return '~' + formatSeconds(estimatedRemaining)
})

const completedDuration = computed(() => {
  if (!job.value) return '--'
  if (job.value.pipeline_seconds) return formatSeconds(job.value.pipeline_seconds)
  // Fallback: calculate from timestamps
  if (job.value.created_at && job.value.completed_at) {
    const start = new Date(job.value.created_at).getTime()
    const end = new Date(job.value.completed_at).getTime()
    return formatSeconds(Math.floor((end - start) / 1000))
  }
  return '--'
})

const chatMessages = computed(() => {
  if (!job.value) return []
  try {
    const raw = job.value.result_chat_log || '[]'
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return Array.isArray(parsed) ? parsed : []
  } catch { return [] }
})

const liveStatus = computed(() => job.value?.live_status || null)
const liveLogLines = computed(() => liveStatus.value?.log_lines || [])
const livePartialChat = computed(() => liveStatus.value?.partial_chat || [])
const liveRound = computed(() => liveStatus.value?.round ?? null)
const liveMaxRounds = computed(() => liveStatus.value?.max_rounds ?? null)
const isLiveStale = computed(() => {
  if (!liveStatus.value?.updated_at) return true
  return (Date.now() / 1000 - liveStatus.value.updated_at) > 120
})
const showLiveActivity = computed(() =>
  isActive.value &&
  !isLiveStale.value &&
  (liveLogLines.value.length > 0 || livePartialChat.value.length > 0)
)

const statusLabel = computed(() => {
  const map = {
    COMPLETED: 'Complete',
    RUNNING: 'Running',
    PROVISIONING: 'Allocating GPU',
    PENDING: 'Queued',
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

async function handleRetry() {
  retrying.value = true
  try {
    const newJob = await retryJob(jobId)
    router.push(`/sim/${newJob.id}`)
  } catch (err) {
    alert(err.response?.data?.detail || 'Retry failed. Please try again.')
    retrying.value = false
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
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}
.animate-shimmer { animation: shimmer 2s infinite; }
</style>
