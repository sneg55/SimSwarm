<template>
  <div class="max-w-3xl mx-auto px-4 py-8">
    <div class="mb-6">
      <router-link to="/dashboard" class="text-sm text-ocean-glow hover:underline">&larr; Back to Dashboard</router-link>
      <h1 class="text-2xl font-bold text-mist-foam mt-2">Simulation Running</h1>
    </div>

    <div v-if="job" class="space-y-6">
      <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h2 class="font-semibold text-mist-foam">{{ job.goal }}</h2>
            <p class="text-sm text-mist-slate capitalize">{{ job.tier }} tier</p>
          </div>
          <span
            class="px-3 py-1 rounded-full text-sm font-medium"
            :class="statusClass(job.status)"
          >
            {{ job.status }}
          </span>
        </div>

        <PipelineProgress
          :current-step="currentStep"
          :completed-steps="completedSteps"
        />

        <p v-if="job.pipeline_stage" class="text-xs text-mist-slate mt-3">
          Stage {{ job.pipeline_stage }} of 5
        </p>
      </div>

      <div v-if="job.status === 'completed'" class="text-center py-4">
        <p class="text-organic-seafoam font-medium mb-3">Simulation complete!</p>
        <router-link
          :to="`/sim/${jobId}/results`"
          class="px-6 py-2 bg-gradient-to-br from-organic-sage to-organic-seafoam text-white rounded-md hover:shadow-[0_0_24px_rgba(16,185,129,0.3)]"
        >
          View Results
        </router-link>
      </div>

      <div v-if="job.status === 'failed'" class="bg-coral/10 border border-coral/20 rounded-2xl p-4">
        <p class="text-coral font-medium">Simulation failed</p>
        <p class="text-coral text-sm mt-1">{{ job.error || 'An unexpected error occurred.' }}</p>
      </div>

      <div v-if="job.messages && job.messages.length > 0">
        <ChatReplay :messages="job.messages" />
      </div>
    </div>

    <div v-else-if="loading" class="text-center py-12 text-mist-slate">
      Loading simulation status...
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import PipelineProgress from '../components/PipelineProgress.vue'
import ChatReplay from '../components/ChatReplay.vue'
import { getJob } from '../api/jobs.js'

const STAGE_STEP_IDS = ['seed', 'research', 'prepare', 'simulate', 'report']

const route = useRoute()
const jobId = route.params.id

const job = ref(null)
const loading = ref(true)
let pollInterval = null

const currentStep = computed(() => {
  if (!job.value || !job.value.pipeline_stage) return null
  const idx = job.value.pipeline_stage - 1
  return STAGE_STEP_IDS[idx] ?? null
})

const completedSteps = computed(() => {
  if (!job.value || !job.value.pipeline_stage) return []
  return STAGE_STEP_IDS.slice(0, job.value.pipeline_stage - 1)
})

async function fetchJob() {
  try {
    job.value = await getJob(jobId)
    if (job.value.status === 'completed' || job.value.status === 'failed') {
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
})

onUnmounted(() => {
  clearInterval(pollInterval)
})

function statusClass(status) {
  const map = {
    completed: 'bg-ocean-glow/10 text-ocean-glow border border-ocean-glow/20',
    running: 'bg-organic-violet/10 text-organic-violet border border-organic-violet/20',
    pending: 'bg-mist-slate/10 text-mist-slate border border-mist-slate/20',
    failed: 'bg-coral/10 text-coral border border-coral/20',
  }
  return map[status] ?? 'bg-mist-depth text-mist-slate'
}
</script>
