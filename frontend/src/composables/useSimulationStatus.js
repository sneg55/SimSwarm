/**
 * Composable for SimulationStatus polling, computed state, and actions.
 * Extracted from SimulationStatus.vue to keep that file under the 300-line limit.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJob, retryJob, retryEnrichment } from '../api/jobs.js'
import {
  STAGE_NAMES,
  STAGE_STEP_IDS,
  TIER_ESTIMATES,
  formatSeconds,
  formatDate,
} from './simulationStatusHelpers.js'

export function useSimulationStatus() {
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

  // ── Derived status flags ──────────────────────────────────────────────────

  const isActive = computed(() =>
    job.value && ['RUNNING', 'PROVISIONING'].includes(job.value.status)
  )

  const currentStep = computed(() => {
    if (!job.value) return null
    if (job.value.status === 'COMPLETED') return null
    if (job.value.status === 'FAILED') return null
    if (['PENDING', 'PROVISIONING'].includes(job.value.status)) return 'research'
    if (!job.value.pipeline_stage) return 'research'
    return STAGE_STEP_IDS[job.value.pipeline_stage - 1] ?? null
  })

  const completedSteps = computed(() => {
    if (!job.value) return []
    if (job.value.status === 'COMPLETED') return [...STAGE_STEP_IDS]
    if (['PENDING', 'PROVISIONING'].includes(job.value.status)) return ['seed']
    if (!job.value.pipeline_stage) return ['seed']
    return STAGE_STEP_IDS.slice(0, job.value.pipeline_stage - 1)
  })

  const currentStageName = computed(() => {
    if (!job.value || !job.value.pipeline_stage) return 'Preparing...'
    return STAGE_NAMES[job.value.pipeline_stage - 1] || 'Processing'
  })

  // ── Time / progress ───────────────────────────────────────────────────────

  const elapsedSeconds = computed(() => {
    if (!job.value || !job.value.created_at) return 0
    return Math.floor((now.value - new Date(job.value.created_at).getTime()) / 1000)
  })

  const elapsed = computed(() => {
    if (!job.value || !job.value.created_at) return '--'
    return formatSeconds(elapsedSeconds.value)
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

  const progressPercent = computed(() => {
    if (!job.value || !job.value.pipeline_stage) return 0
    const stageBase = (job.value.pipeline_stage - 1) * 20
    const estimates = TIER_ESTIMATES[job.value.tier] || TIER_ESTIMATES.medium
    const currentEstimate = estimates[job.value.pipeline_stage - 1] || 300
    const elapsedInStage = elapsedSeconds.value -
      estimates.slice(0, job.value.pipeline_stage - 1).reduce((a, b) => a + b, 0)
    const stageProgress = Math.min(0.95, Math.max(0, elapsedInStage / currentEstimate))
    return Math.min(99, Math.round(stageBase + stageProgress * 20))
  })

  const eta = computed(() => {
    if (!job.value || !job.value.pipeline_stage || !job.value.tier) return '--'
    const total = estimatedTotalSeconds.value
    const el = elapsedSeconds.value
    if (el <= 0 || total <= 0) return '--'
    const pct = progressPercent.value / 100
    if (pct <= 0.01) return '~' + formatSeconds(total)
    const estimatedRemaining = Math.max(0, Math.round((el / pct) * (1 - pct)))
    if (estimatedRemaining < 30) return '< 1 min'
    return '~' + formatSeconds(estimatedRemaining)
  })

  const completedDuration = computed(() => {
    if (!job.value) return '--'
    if (job.value.pipeline_seconds) return formatSeconds(job.value.pipeline_seconds)
    if (job.value.created_at && job.value.completed_at) {
      const start = new Date(job.value.created_at).getTime()
      const end = new Date(job.value.completed_at).getTime()
      return formatSeconds(Math.floor((end - start) / 1000))
    }
    return '--'
  })

  // ── Live status ───────────────────────────────────────────────────────────

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

  // ── Chat / citations ──────────────────────────────────────────────────────

  const chatMessages = computed(() => {
    if (!job.value) return []
    try {
      const raw = job.value.result_chat_log || '[]'
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      return Array.isArray(parsed) ? parsed : []
    } catch { return [] }
  })

  // ── Status badge helpers ──────────────────────────────────────────────────

  const statusLabel = computed(() => {
    const map = {
      COMPLETED: 'Complete', RUNNING: 'Running', PROVISIONING: 'Allocating GPU',
      PENDING: 'Queued', FAILED: 'Failed', REFUNDED: 'Refunded',
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
    if (isActive.value || job.value?.status === 'PROVISIONING')
      return 'bg-organic-violet animate-[breathe_2.5s_ease-in-out_infinite]'
    if (job.value?.status === 'PENDING')
      return 'bg-mist-slate animate-[breathe_3s_ease-in-out_infinite]'
    if (job.value?.status === 'COMPLETED') return 'bg-ocean-glow'
    if (job.value?.status === 'FAILED') return 'bg-coral'
    return 'bg-mist-slate'
  })

  // ── Actions ───────────────────────────────────────────────────────────────

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

  async function retryEnrich() {
    enrichRetrying.value = true
    try {
      await retryEnrichment(jobId)
    } catch { /* ignore */ }
    enrichRetrying.value = false
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  onMounted(() => {
    fetchJob()
    pollInterval = setInterval(fetchJob, 3000)
    tickInterval = setInterval(() => { now.value = Date.now() }, 1000)
  })

  onUnmounted(() => {
    clearInterval(pollInterval)
    clearInterval(tickInterval)
  })

  return {
    jobId, job, loading, retrying, researchOpen, enrichRetrying,
    isActive, currentStep, completedSteps, currentStageName,
    elapsed, elapsedSeconds, estimatedTotal, progressPercent, eta, completedDuration,
    liveLogLines, livePartialChat, liveRound, liveMaxRounds, isLiveStale, showLiveActivity,
    chatMessages,
    statusLabel, statusBadgeClass, statusDotClass,
    handleRetry, retryEnrich, formatDate,
  }
}
