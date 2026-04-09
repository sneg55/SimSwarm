<template>
  <div class="max-w-[640px] mx-auto px-6 pt-24 pb-16">
    <WizardProgress :current="step" @go="goToStep" />

    <div v-if="error" class="mt-4 p-3 bg-coral/10 border border-coral/20 text-coral rounded-xl text-sm">
      {{ error }}
    </div>

    <!-- Step 1 -->
    <div v-if="step === 1" class="step-anim">
      <WizardSeed v-model:seedText="seedText" />
      <div class="flex justify-between text-xs mt-1">
        <span :class="seedQualityClass">{{ seedQualityMessage }}</span>
        <span class="text-mist-slate">{{ seedText.length.toLocaleString() }} / 50,000 chars</span>
      </div>
      <label class="flex items-center gap-3 mt-4 cursor-pointer group">
        <input type="checkbox" v-model="enrichWeb"
          class="w-4 h-4 rounded border-mist-depth bg-ocean-abyss text-ocean-cyan focus:ring-ocean-cyan/30 accent-ocean-cyan">
        <div>
          <span class="text-sm text-mist-drift group-hover:text-mist-foam transition-colors">Enrich with web research</span>
          <p class="text-xs text-mist-slate mt-0.5">Automatically research your topic using web and social media search</p>
        </div>
      </label>
      <div class="wizard-nav">
        <div />
        <button @click="goToStep(2)" :disabled="seedText.length < MIN_SEED_CHARS || seedText.length > MAX_SEED_CHARS" class="btn-next">
          Continue →
        </button>
      </div>
    </div>

    <!-- Step 2 -->
    <div v-if="step === 2" class="step-anim">
      <WizardGoal v-model:goal="goal" v-model:forecastDays="forecastDays" :seed-text="seedText" />
      <div class="wizard-nav">
        <button @click="goToStep(1)" class="btn-back">← Back</button>
        <button @click="goToStep(3)" :disabled="!goal.trim()" class="btn-next">
          Continue →
        </button>
      </div>
    </div>

    <!-- Step 3 -->
    <div v-if="step === 3" class="step-anim">
      <WizardLaunch v-model:tier="selectedTier" :forecastDays="forecastDays" />
      <div class="wizard-nav">
        <button @click="goToStep(2)" class="btn-back">← Back</button>
        <button @click="handleSubmit" :disabled="!canSubmit || loading" class="btn-launch">
          {{ loading ? 'Starting...' : 'Run Simulation' }} 🚀
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import WizardProgress from '../components/wizard/WizardProgress.vue'
import WizardSeed from '../components/wizard/WizardSeed.vue'
import WizardGoal from '../components/wizard/WizardGoal.vue'
import WizardLaunch from '../components/wizard/WizardLaunch.vue'
import { useCreditsStore } from '../stores/credits.js'
import { createJob, createDraft, updateDraft, launchDraft, getJob } from '../api/jobs.js'
import { getBalance } from '../api/billing.js'

const router = useRouter()
const route = useRoute()
const creditsStore = useCreditsStore()

const draftId = ref(null)
const draftLoading = ref(false)

onMounted(async () => {
  try {
    const data = await getBalance()
    creditsStore.setBalance(data.balance ?? data)
  } catch (err) {
    console.error('Failed to load balance:', err)
  }

  const resumeId = route.query.draft
  if (!resumeId) return

  draftLoading.value = true
  try {
    const job = await getJob(resumeId)
    if (job.status !== 'DRAFT') return

    draftId.value = job.id
    seedText.value = job.seed_text || ''
    goal.value = job.goal || ''
    selectedTier.value = job.tier || null
    enrichWeb.value = job.enrich_web ?? true
    forecastDays.value = job.forecast_days ?? null

    // Infer starting step
    if (job.goal) {
      step.value = 3
    } else if (job.seed_text) {
      step.value = 2
    } else {
      step.value = 1
    }
  } catch (err) {
    console.error('Failed to load draft:', err)
  } finally {
    draftLoading.value = false
  }
})

const step = ref(1)
const seedText = ref('')
const goal = ref('')
const selectedTier = ref(null)
const enrichWeb = ref(true)
const forecastDays = ref(null)
const loading = ref(false)
const error = ref('')

const MIN_SEED_CHARS = 500
const GOOD_SEED_CHARS = 1500
const MAX_SEED_CHARS = 50000

const seedQualityMessage = computed(() => {
  const len = seedText.value.length
  if (len === 0) return ''
  if (len < MIN_SEED_CHARS) return '\u26A0 Seed is too short \u2014 simulations need more context for good results'
  if (len < GOOD_SEED_CHARS) return '\u26A1 Seed could use more detail \u2014 consider adding background context'
  if (len > MAX_SEED_CHARS) return '\u26A0 Seed exceeds maximum \u2014 please trim to 50,000 characters'
  return '\u2713 Seed looks good!'
})

const seedQualityClass = computed(() => {
  const len = seedText.value.length
  if (len === 0) return 'text-mist-slate'
  if (len < MIN_SEED_CHARS) return 'text-amber-400'
  if (len < GOOD_SEED_CHARS) return 'text-amber-300'
  if (len > MAX_SEED_CHARS) return 'text-red-400'
  return 'text-emerald-400'
})

const canSubmit = computed(() =>
  seedText.value.trim() &&
  seedText.value.length >= MIN_SEED_CHARS &&
  seedText.value.length <= MAX_SEED_CHARS &&
  goal.value.trim() &&
  selectedTier.value &&
  creditsStore.canAfford(selectedTier.value)
)

async function goToStep(n) {
  if (n < step.value) {
    step.value = n
    return
  }

  // Auto-save on forward step transitions
  error.value = ''
  try {
    if (step.value === 1 && n === 2) {
      if (!draftId.value) {
        const draft = await createDraft({
          seed_text: seedText.value,
          enrich_web: enrichWeb.value,
        })
        draftId.value = draft.id
      } else {
        await updateDraft(draftId.value, {
          seed_text: seedText.value,
          enrich_web: enrichWeb.value,
        })
      }
    } else if (step.value === 2 && n === 3) {
      if (draftId.value) {
        await updateDraft(draftId.value, {
          goal: goal.value,
          forecast_days: forecastDays.value,
        })
      }
    }
  } catch (err) {
    error.value = 'Failed to save draft. Please try again.'
    return
  }

  step.value = n
}

async function handleSubmit() {
  await nextTick()
  loading.value = true
  error.value = ''
  try {
    if (draftId.value) {
      await updateDraft(draftId.value, { tier: selectedTier.value })
      const job = await launchDraft(draftId.value)
      creditsStore.deduct(creditsStore.getTierCost(selectedTier.value))
      router.push(`/sim/${job.id}`)
    } else {
      const job = await createJob({
        seed_text: seedText.value,
        goal: goal.value,
        tier: selectedTier.value,
        enrich_web: enrichWeb.value,
        forecast_days: forecastDays.value,
      })
      creditsStore.deduct(creditsStore.getTierCost(selectedTier.value))
      router.push(`/sim/${job.id}`)
    }
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to start simulation.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.btn-next {
  @apply px-8 py-3 rounded-xl text-[15px] font-bold text-white bg-gradient-to-br from-ocean-cyan to-cyan-500 transition-all ease-spring hover:-translate-y-0.5 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none;
  box-shadow: 0 0 16px rgba(34, 211, 238, 0.3);
}
.btn-next:not(:disabled):hover {
  box-shadow: 0 0 24px rgba(34, 211, 238, 0.5);
}
.btn-back {
  @apply text-sm font-medium text-mist-drift hover:text-mist-foam transition-colors;
}
.btn-launch {
  @apply px-8 py-3 rounded-xl text-[15px] font-bold text-white bg-gradient-to-br from-coral to-coral-amber transition-all ease-spring hover:-translate-y-0.5 disabled:opacity-40 disabled:cursor-not-allowed;
  box-shadow: 0 0 16px rgba(255, 107, 107, 0.3);
}
.btn-launch:not(:disabled):hover {
  box-shadow: 0 0 24px rgba(255, 107, 107, 0.5);
}
.wizard-nav {
  @apply flex items-center justify-between mt-8 pt-5 border-t border-mist-depth;
}
.step-anim {
  animation: fadeSlideIn 0.4s ease-out;
}
@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
