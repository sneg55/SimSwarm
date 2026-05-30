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
        <PipelineProgress :current-step="currentStep" :completed-steps="completedSteps" />

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
                {{ liveRound }} <span class="text-mist-slate font-normal">/ {{ liveMaxRounds ?? '--' }}</span>
              </span>
            </div>
          </template>

          <!-- Pending / provisioning state -->
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

      <!-- Live Activity feed -->
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

      <!-- Web research unavailable notice -->
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
        <p class="text-sm text-mist-drift">{{ job.error_message || 'An unexpected error occurred. Please try again.' }}</p>
        <button
          @click="handleRetry"
          :disabled="retrying"
          class="inline-block mt-3 text-sm text-ocean-glow hover:underline disabled:opacity-50 disabled:cursor-wait"
        >{{ retrying ? 'Retrying...' : 'Retry this simulation' }} &rarr;</button>
      </div>

      <!-- Live chat replay -->
      <div v-if="isActive && chatMessages.length > 0">
        <ChatReplay :messages="chatMessages" :start-expanded="true" />
      </div>
    </div>
  </div>
</template>

<script setup>
import PipelineProgress from '../components/PipelineProgress.vue'
import ChatReplay from '../components/ChatReplay.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ReportViewer from '../components/ReportViewer.vue'
import LiveActivity from '../components/LiveActivity.vue'
import { useSimulationStatus } from '../composables/useSimulationStatus.js'

const {
  jobId, job, loading, retrying, researchOpen, enrichRetrying,
  isActive, currentStep, completedSteps, currentStageName,
  elapsed, elapsedSeconds, estimatedTotal, progressPercent, eta, completedDuration,
  liveLogLines, livePartialChat, liveRound, liveMaxRounds, isLiveStale, showLiveActivity,
  chatMessages,
  statusLabel, statusBadgeClass, statusDotClass,
  handleRetry, retryEnrich, formatDate,
} = useSimulationStatus()
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
