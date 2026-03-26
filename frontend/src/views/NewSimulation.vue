<template>
  <div class="max-w-3xl mx-auto px-4 py-8">
    <div class="mb-6">
      <router-link to="/dashboard" class="text-sm text-blue-600 hover:underline">&larr; Back to Dashboard</router-link>
      <h1 class="text-2xl font-bold text-gray-900 mt-2">New Simulation</h1>
    </div>

    <CreditWarning />

    <form @submit.prevent="handleSubmit" class="space-y-6 mt-6">
      <div v-if="error" class="bg-red-50 text-red-700 p-3 rounded text-sm">{{ error }}</div>

      <SeedUploader @update="handleSeedUpdate" />

      <div>
        <label for="goal" class="block text-sm font-medium text-gray-700">Research Goal</label>
        <textarea
          id="goal"
          v-model="goal"
          required
          rows="3"
          placeholder="Describe what you want to learn or analyze..."
          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      <TierSelector @select="selectedTier = $event" />

      <div class="flex items-center justify-between pt-4">
        <div class="text-sm text-gray-500">
          Cost: <strong>{{ selectedTier ? creditsStore.getTierCost(selectedTier) : 0 }} credits</strong>
        </div>
        <button
          type="submit"
          :disabled="!canSubmit || loading"
          class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ loading ? 'Starting...' : 'Run Simulation' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import CreditWarning from '../components/CreditWarning.vue'
import SeedUploader from '../components/SeedUploader.vue'
import TierSelector from '../components/TierSelector.vue'
import { useCreditsStore } from '../stores/credits.js'
import { createJob } from '../api/jobs.js'

const router = useRouter()
const creditsStore = useCreditsStore()

const seedData = ref(null)
const goal = ref('')
const selectedTier = ref(null)
const loading = ref(false)
const error = ref('')

const canSubmit = computed(() =>
  seedData.value &&
  goal.value.trim() &&
  selectedTier.value &&
  creditsStore.canAfford(selectedTier.value)
)

function handleSeedUpdate(data) {
  seedData.value = data
}

async function handleSubmit() {
  loading.value = true
  error.value = ''
  try {
    const seedContent = seedData.value?.content || ''
    const payload = {
      goal: goal.value,
      tier: selectedTier.value,
      seed_text: seedContent,
    }
    const job = await createJob(payload)
    router.push(`/sim/${job.id}`)
  } catch (err) {
    error.value = err.response?.data?.message || 'Failed to start simulation.'
  } finally {
    loading.value = false
  }
}
</script>
